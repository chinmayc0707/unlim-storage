with open('app.py', 'r') as f:
    content = f.read()

# Check imports
if "from datetime import datetime, timedelta" not in content:
    content = content.replace("from datetime import timedelta", "from datetime import datetime, timedelta")
    # if neither was there
    if "from datetime import datetime, timedelta" not in content:
         content = "from datetime import datetime, timedelta\n" + content

with open('app.py', 'w') as f:
    f.write(content)
