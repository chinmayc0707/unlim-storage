# Clean up requirements.txt and save it back properly.
# We need to make sure we don't destroy its encoding or we convert it to UTF-8.
import codecs

with codecs.open("requirements.txt", "r", encoding="utf-16-le", errors='ignore') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    line = line.strip()
    if line:
        # Ignore lines like "Flask\x00" due to utf-16 artifacts if any
        new_lines.append(line.replace('\x00', ''))

# Append the ones we installed
if "PyJWT==2.8.0" not in new_lines:
    new_lines.append("PyJWT==2.8.0")
if "requests" not in new_lines:
    new_lines.append("requests")
if "psycopg2-binary" not in new_lines:
    new_lines.append("psycopg2-binary")
if "werkzeug" not in "\n".join(new_lines).lower():
    new_lines.append("Werkzeug")

# Write back in standard utf-8
with open("requirements.txt", "w", encoding="utf-8") as f:
    for line in new_lines:
        if line.strip():
            f.write(line.strip() + "\n")
