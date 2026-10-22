import os
import time

def scan_walk(target):
    sz = 0
    count = 0
    for root, dirs, files in os.walk(target):
        for f in files:
            count += 1
            fpath = os.path.join(root, f)
            try:
                sz += os.stat(fpath).st_size
            except:
                pass
    return count, sz

def scan_scandir(target):
    sz = 0
    count = 0
    dirs = [target]
    while dirs:
        current_dir = dirs.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        count += 1
                        try:
                            sz += entry.stat(follow_symlinks=False).st_size
                        except:
                            pass
        except:
            pass
    return count, sz

target = os.getcwd() # Or some big dir
# Create some dummy files
os.makedirs("dummy_dir/sub1", exist_ok=True)
os.makedirs("dummy_dir/sub2", exist_ok=True)
for i in range(10000):
    with open(f"dummy_dir/sub1/file_{i}.txt", "w") as f:
        f.write("a" * 10)
    with open(f"dummy_dir/sub2/file_{i}.txt", "w") as f:
        f.write("a" * 10)


t0 = time.time()
c1, s1 = scan_walk("dummy_dir")
t1 = time.time()
c2, s2 = scan_scandir("dummy_dir")
t2 = time.time()

print(f"walk: {c1} files, {s1} bytes, time: {t1-t0:.4f}")
print(f"scandir: {c2} files, {s2} bytes, time: {t2-t1:.4f}")
