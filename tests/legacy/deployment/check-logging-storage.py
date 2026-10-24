"""Read-only disk guard for the existing lab. Never deletes data or prunes Docker."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,json,shutil,subprocess,sys
def run(cmd):return subprocess.check_output(cmd,text=True).strip()
root=shutil.disk_usage('/');project='dtc245200016_btl_tkqt_htpm' if len(sys.argv)<2 or sys.argv[1]=='main' else 'greenshop-m2-qa'
volume=project+'_loki_data'
kib=int(run(['docker','run','--rm','--network','none','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','-v',volume+':/data:ro','busybox:1.37.0-musl','du','-sk','/data']).split()[0])
used=100*root.used/(root.used+root.free)
d={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'project':project,'host_free_bytes':root.free,'host_disk_used_percent':round(used,2),'loki_volume_bytes':kib*1024,'loki_storage_soft_budget_bytes':512*1024**2,'warning':used>85 or kib>512*1024,'critical':root.free<1024**3,'action':'Read-only observation; investigate noise/capacity. Never prune business volumes or manually remove Loki chunks.'}
print(json.dumps(d,indent=2));sys.exit(2 if d['critical'] else 0)
