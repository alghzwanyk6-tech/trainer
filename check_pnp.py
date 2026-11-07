import subprocess
p = subprocess.run(['powershell', '-Command', 'Get-PnpDevice -Status OK | Select-Object Class, FriendlyName, InstanceId | Format-Table -AutoSize'], capture_output=True, text=True, errors='ignore')
with open('pnp_list.txt', 'w', encoding='utf-8') as f:
    f.write(p.stdout)
print("Saved to pnp_list.txt")
