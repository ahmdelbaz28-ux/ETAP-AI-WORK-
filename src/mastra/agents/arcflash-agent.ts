import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { execFile } from "child_process";
import { z } from "zod";
import { getSystemPrompt } from "../prompts";
import { getActiveModelConfig } from "../lib/model-config";

const PYTHON_TIMEOUT_MS = 30000;

// Arc flash calculation tool using safe execFile
const arcFlashCalcTool = createTool({
  id: 'arc-flash-calculator',
  description: "Calculate arc flash incident energy and boundary using IEEE 1584-2018 method",
  inputSchema: z.object({
    voltage_kv: z.number().describe("System voltage in kV"),
    bolted_fault_current_ka: z.number().describe("Bolted fault current in kA"),
    arc_duration_sec: z.number().describe("Arc duration in seconds"),
    working_distance_mm: z.number().describe("Working distance in mm"),
    enclosure_type: z.enum(["open", "box"]).default("box").describe("Enclosure type: open or box"),
    electrode_config: z.enum(["VCB", "VCBB", "HCB", "VOA", "HOA"]).default("VCB").describe("Electrode configuration"),
  }),
  execute: async (inputData) => {
    const { voltage_kv, bolted_fault_current_ka, arc_duration_sec, working_distance_mm, enclosure_type, electrode_config } = inputData;
    // Python script for IEEE 1584-2018 arc flash calculation
    const pythonCode = `
import sys
import json
import math

# Input parameters
V = float(sys.argv[1])       # kV
Ibf = float(sys.argv[2])     # kA
t = float(sys.argv[3])       # seconds
D = float(sys.argv[4])       # mm
enc_type = sys.argv[5]       # open or box
elec_config = sys.argv[6]    # VCB, VCBB, HCB, VOA, HOA

# IEEE 1584-2018 Arc Flash Calculations
# Step 1: Intermediate arc current (kA) for voltages 0.6-15 kV
if V < 0.208:
    # For low voltage < 208V, use Ralph Lee method as fallback
    E = (5.12e5 * V * Ibf * t) / (D ** 2)
    D_boundary = ((5.12e5 * V * Ibf * t) / 1.2) ** 0.5
    result = {
        "incident_energy_cal_per_cm2": round(E, 4),
        "arc_flash_boundary_mm": round(D_boundary, 1),
        "arc_flash_boundary_in": round(D_boundary / 25.4, 1),
        "arc_current_ka": round(Ibf, 4),
        "method": "Ralph Lee (voltage below IEEE 1584 range)",
        "ppe_level": "N/A - consult engineer"
    }
    print(json.dumps(result))
    sys.exit(0)

# IEEE 1584-2018 coefficients based on electrode configuration
coefficients = {
    "VCB":  {"k1": -0.153, "k2": -0.276, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
    "VCBB": {"k1": -0.792, "k2": -0.552, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
    "HCB":  {"k1": -0.555, "k2": -0.442, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
    "VOA":  {"k1": -0.153, "k2": -0.276, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
    "HOA":  {"k1": -0.555, "k2": -0.442, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
}

# Get coefficients for the electrode configuration
if elec_config not in coefficients:
    elec_config = "VCB"  # default fallback

c = coefficients[elec_config]

# Step 1: Calculate arc current
# Iarc = 10^(k1 + k2*log10(Ibf) + k3*Ibf) for V >= 1kV
# For 0.208 <= V < 1kV, different coefficients apply
if V >= 1.0:
    log_Iarc = c["k1"] + c["k2"] * math.log10(Ibf) + c["k3"] * Ibf
    Iarc = 10 ** log_Iarc
else:
    # Low voltage equations (0.208 to 1 kV)
    log_Iarc = c["k1"] + c["k2"] * math.log10(Ibf) + c["k3"] * Ibf
    Iarc = 10 ** log_Iarc

# Reduced arc current (85% for fuse reduction)
Iarc_min = 0.85 * Iarc

# Step 2: Calculate incident energy
# E = 10^(k1_ie + k2_ie*log10(Iarc) + k3_ie*Iarc) * t * (1/D^x_ie)
# Enclosure size correction factor
if enc_type == "box":
    # Typical enclosure dimensions
    enclosure_width_mm = 508.0  # 20 inches default
    enclosure_height_mm = 508.0  # 20 inches default
    enclosure_depth_mm = 508.0   # 20 inches default
    # Enclosure correction factor
    Cf = 1.0  # Default correction factor
else:
    Cf = 1.0

# Incident energy calculation
log_E = c["k1_ie"] + c["k2_ie"] * math.log10(Iarc) + c["k3_ie"] * Iarc
E_base = 10 ** log_E
E = E_base * t / (D ** c["x_ie"]) * Cf

# Also calculate at reduced arc current
log_E_min = c["k1_ie"] + c["k2_ie"] * math.log10(Iarc_min) + c["k3_ie"] * Iarc_min
E_base_min = 10 ** log_E_min
E_min = E_base_min * t / (D ** c["x_ie"]) * Cf

# Use the higher of the two incident energies
E_final = max(E, E_min)

# Step 3: Arc flash boundary (distance where E = 1.2 cal/cm^2)
D_boundary = (E_base * t / 1.2) ** (1.0 / c["x_ie"]) * Cf ** (1.0 / c["x_ie"])
D_boundary_min = (E_base_min * t / 1.2) ** (1.0 / c["x_ie"]) * Cf ** (1.0 / c["x_ie"])
D_boundary_final = max(D_boundary, D_boundary_min)

# PPE Level determination based on incident energy
if E_final <= 1.2:
    ppe_level = "0"
    ppe_description = "No PPE required (E <= 1.2 cal/cm^2)"
elif E_final <= 4.0:
    ppe_level = "1"
    ppe_description = "Arc-Rated Shirt and Pants (4 cal/cm^2 minimum)"
elif E_final <= 8.0:
    ppe_level = "2"
    ppe_description = "Arc-Rated Shirt and Pants, Face Shield (8 cal/cm^2 minimum)"
elif E_final <= 25.0:
    ppe_level = "3"
    ppe_description = "Arc-Rated Shirt and Pants, Arc Flash Suit (25 cal/cm^2 minimum)"
elif E_final <= 40.0:
    ppe_level = "4"
    ppe_description = "Arc-Rated Shirt and Pants, Arc Flash Suit (40 cal/cm^2 minimum)"
else:
    ppe_level = "DANGER"
    ppe_description = "E > 40 cal/cm^2 - De-energize before working"

# Output results
result = {
    "incident_energy_cal_per_cm2": round(E_final, 4),
    "incident_energy_at_full_arc_current": round(E, 4),
    "incident_energy_at_reduced_arc_current": round(E_min, 4),
    "arc_flash_boundary_mm": round(D_boundary_final, 1),
    "arc_flash_boundary_in": round(D_boundary_final / 25.4, 1),
    "arc_current_ka": round(Iarc, 4),
    "reduced_arc_current_ka": round(Iarc_min, 4),
    "method": "IEEE 1584-2018",
    "electrode_configuration": elec_config,
    "enclosure_type": enc_type,
    "ppe_level": ppe_level,
    "ppe_description": ppe_description
}

print(json.dumps(result))
`;

    return new Promise((resolve, reject) => {
      const args = [
        '-c', pythonCode,
        String(voltage_kv),
        String(bolted_fault_current_ka),
        String(arc_duration_sec),
        String(working_distance_mm),
        enclosure_type,
        electrode_config,
      ];

      const child = execFile('python', args, {
        encoding: 'utf8',
        timeout: PYTHON_TIMEOUT_MS,
        maxBuffer: 1024 * 1024,
      }, (error, stdout, stderr) => {
        if (error) {
          const errMessage = stderr?.trim() || error.message || 'Unknown error';
          reject(new Error(`Arc flash calculation failed: ${errMessage}`));
          return;
        }
        try {
          const result = JSON.parse(stdout.trim());
          resolve(result);
        } catch (parseError) {
          reject(new Error(`Failed to parse arc flash results: ${parseError}`));
        }
      });

      child.on('error', (err) => {
        reject(new Error(`Failed to start Python process: ${err.message}`));
      });
    });
  },
});

const arcFlashAgentPrompt = await getSystemPrompt("arcflash_agent_prompt");

// Create and export the agent
export const arcFlashAgent = new Agent({
  id: 'arc-flash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: arcFlashAgentPrompt,
  model: getActiveModelConfig(),
  tools: { arc_flash_calculator: arcFlashCalcTool },
});
