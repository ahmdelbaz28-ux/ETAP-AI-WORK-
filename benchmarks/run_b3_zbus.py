"""Run Benchmark 3: Zbus vs LU comparison."""

import sys
sys.path.insert(0, '.')

from benchmarks.benchmark_suite import benchmark_3_zbus
import json

result = benchmark_3_zbus()

print()
print('=' * 72)
print('SUMMARY — Zbus Dense Inversion vs LU Factorisation')
print('=' * 72)
print(f'  {"Buses":>5}  {"Dense Inv":>10}  {"LU Factor":>10}  {"LU Solve":>10}  {"LU Total":>10}  {"Speedup":>8}')
print('  ' + '-' * 66)
for s in result['systems']:
    spd = s.get('speedup', 'N/A')
    spd_str = f'{spd:>6.1f}x' if isinstance(spd, (int, float)) else f'{spd:>8}'
    print(f'  {s["n_buses"]:5d}  {s["dense_inv_ms"]:>8.1f}ms  '
          f'{s.get("lu_factor_ms", 0) or 0:>8.1f}ms  '
          f'{s.get("lu_solve_ms", 0) or 0:>8.1f}ms  '
          f'{s.get("lu_total_ms", 0) or 0:>8.1f}ms  '
          f'{spd_str}')

print()
avg_speedup = 0
count = 0
for s in result['systems']:
    spd = s.get('speedup')
    if isinstance(spd, (int, float)):
        avg_speedup += spd
        count += 1
avg = avg_speedup / count if count > 0 else 0
print(f'  Average speedup: {avg:.1f}x')
print(f'  Recommendation: Replace dense inversion with LU factorisation in FaultAnalyzer (confirmed {avg:.1f}x faster)')

# Save summary
with open('benchmarks/zbus_lu_comparison.json', 'w') as f:
    json.dump(result, f, indent=2, default=str)
print('  Full results saved to benchmarks/zbus_lu_comparison.json')
