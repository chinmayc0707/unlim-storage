import re
with open("requirements.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    line = line.strip()
    # remove garbage or weird characters
    line = re.sub(r'[^\x00-\x7F]+', '', line)
    if line:
        if line not in new_lines:
            new_lines.append(line)

with open("requirements.txt", "w", encoding="utf-8") as f:
    for line in new_lines:
        f.write(line + "\n")
