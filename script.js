// AhmedETAP Power Grid Animation System
// =======================================
// Enhanced with GSAP for engineering aesthetic

// Initialize GSAP plugins
gsap.registerPlugin(ScrollTrigger, TextPlugin, MotionPathPlugin);

// Canvas setup
const canvas = document.getElementById('grid-canvas');
const ctx = canvas.getContext('2d');
let w, h;

// Power system state
const powerSystem = {
  gridActive: true,
  nodes: [],
  connections: [],
  particles: [],
  powerFlows: []
};

// Resize canvas
function resize() {
  w = canvas.width = window.innerWidth;
  h = canvas.height = window.innerHeight;
  
  // Reinitialize power system
  initPowerSystem();
}
window.addEventListener('resize', resize);
resize();

// Initialize power system
function initPowerSystem() {
  // Clear existing
  powerSystem.nodes = [];
  powerSystem.connections = [];
  powerSystem.particles = [];
  powerSystem.powerFlows = [];
  
  // Create grid nodes (power substations)
  const gridSize = 80;
  for (let x = 0; x < w; x += gridSize) {
    for (let y = 0; y < h; y += gridSize) {
      powerSystem.nodes.push({
        x, y,
        size: 2 + Math.random() * 3,
        pulse: Math.random(),
        type: Math.random() > 0.7 ? 'transformer' : 'substation'
      });
    }
  }
  
  // Create connections (power lines)
  for (let i = 0; i < powerSystem.nodes.length; i++) {
    for (let j = i + 1; j < powerSystem.nodes.length; j++) {
      const dx = powerSystem.nodes[i].x - powerSystem.nodes[j].x;
      const dy = powerSystem.nodes[i].y - powerSystem.nodes[j].y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < 150) {
        powerSystem.connections.push({
          from: i,
          to: j,
          distance,
          flow: 0,
          flowDirection: Math.random() > 0.5 ? 1 : -1
        });
      }
    }
  }
  
  // Create particles (electrons)
  for (let i = 0; i < 50; i++) {
    powerSystem.particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      size: 1 + Math.random() * 2,
      speed: 0.5 + Math.random() * 1.5,
      direction: Math.random() * Math.PI * 2,
      velocity: {
        x: Math.cos(Math.random() * Math.PI * 2) * (0.5 + Math.random() * 1.5),
        y: Math.sin(Math.random() * Math.PI * 2) * (0.5 + Math.random() * 1.5)
      }
    });
  }
}

// Create GSAP animations
function createAnimations() {
  // Animate grid nodes
  gsap.to(powerSystem.nodes, {
    duration: 3,
    pulse: 1,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut",
    stagger: {
      amount: 2,
      grid: "auto",
      from: "random"
    },
    onUpdate: function() {
      // Update node properties
      powerSystem.nodes.forEach((node, i) => {
        node.size = 2 + this.targets()[i].pulse * 3;
      });
    }
  });
  
  // Animate power flows
  powerSystem.connections.forEach((conn, i) => {
    gsap.to(conn, {
      flow: 1,
      duration: 2 + Math.random() * 2,
      repeat: -1,
      yoyo: true,
      ease: "sine.inOut",
      delay: Math.random() * 2,
      onUpdate: function() {
        conn.flow = this.targets()[0].flow;
      }
    });
  });
  
  // Animate particles
  gsap.to(powerSystem.particles, {
    duration: 0.1,
    repeat: -1,
    ease: "none",
    onUpdate: function() {
      powerSystem.particles.forEach((particle, i) => {
        // Update position
        particle.x += particle.velocity.x;
        particle.y += particle.velocity.y;
        
        // Boundary check
        if (particle.x < 0 || particle.x > w) particle.velocity.x *= -1;
        if (particle.y < 0 || particle.y > h) particle.velocity.y *= -1;
      });
    }
  });
}

// Draw power system
function drawPowerSystem() {
  // Clear canvas with dark gradient
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, '#0a0e1a');
  gradient.addColorStop(1, '#0f1525');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, w, h);
  
  // Draw connections (power lines)
  powerSystem.connections.forEach(conn => {
    const fromNode = powerSystem.nodes[conn.from];
    const toNode = powerSystem.nodes[conn.to];
    
    // Calculate flow position
    const flowX = fromNode.x + (toNode.x - fromNode.x) * conn.flow * conn.flowDirection;
    const flowY = fromNode.y + (toNode.y - fromNode.y) * conn.flow * conn.flowDirection;
    
    // Draw power line
    ctx.beginPath();
    ctx.moveTo(fromNode.x, fromNode.y);
    ctx.lineTo(toNode.x, toNode.y);
    ctx.strokeStyle = `rgba(70, 120, 200, ${0.05 + conn.flow * 0.1})`;
    ctx.lineWidth = 0.5 + conn.flow * 1.5;
    ctx.stroke();
    
    // Draw flow indicator
    ctx.beginPath();
    ctx.arc(flowX, flowY, 1 + conn.flow * 2, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(0, 212, 255, ${0.5 + conn.flow * 0.5})`;
    ctx.fill();
  });
  
  // Draw nodes (substations/transformers)
  powerSystem.nodes.forEach(node => {
    // Draw node
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
    
    // Different colors for different node types
    if (node.type === 'transformer') {
      ctx.fillStyle = '#f59e0b'; // Amber for transformers
    } else {
      ctx.fillStyle = '#00d4ff'; // Cyan for substations
    }
    
    ctx.fill();
    
    // Draw pulse effect
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.size * 2, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0, 212, 255, ${0.2 * (1 - node.size / 5)})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  });
  
  // Draw particles (electrons)
  powerSystem.particles.forEach(particle => {
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(0, 212, 255, ${0.5 + Math.random() * 0.3})`;
    ctx.fill();
  });
  
  // Draw scanline effect
  const scanline = {
    y: (Date.now() * 0.1) % h,
    height: 40
  };
  ctx.fillStyle = 'rgba(0, 212, 255, 0.05)';
  ctx.fillRect(0, scanline.y, w, scanline.height);
  
  requestAnimationFrame(drawPowerSystem);
}

// Entrance animations
function animateEntrance() {
  // Login card entrance
  const loginCard = document.querySelector('.login-card');
  gsap.from(loginCard, {
    y: 50,
    opacity: 0,
    duration: 1.2,
    delay: 0.3,
    ease: "back.out(1.7)"
  });
  
  // Logo entrance
  const logo = document.querySelector('.logo');
  gsap.from(logo, {
    scale: 0.8,
    opacity: 0,
    duration: 1,
    delay: 0.5,
    ease: "back.out(1.7)"
  });
  
  // Title entrance
  const title = document.querySelector('h1');
  gsap.from(title, {
    y: 20,
    opacity: 0,
    duration: 0.8,
    delay: 0.7,
    ease: "back.out(1.7)"
  });
  
  // Form elements entrance
  const formElements = document.querySelectorAll('.login-form input, .login-form button');
  gsap.from(formElements, {
    y: 20,
    opacity: 0,
    duration: 0.6,
    stagger: 0.1,
    delay: 0.9,
    ease: "back.out(1.7)"
  });
  
  // Hand illustrations entrance
  const hands = document.querySelectorAll('.hand');
  gsap.from(hands, {
    y: 30,
    opacity: 0,
    duration: 1,
    stagger: 0.2,
    delay: 1.1,
    ease: "back.out(1.7)"
  });
}

// Initialize
createAnimations();
animateEntrance();
drawPowerSystem();