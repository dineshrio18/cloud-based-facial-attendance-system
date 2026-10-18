import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. GET /login
login_page = opener.open('http://127.0.0.1:5000/login').read().decode('utf-8')
csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', login_page).group(1)

# 2. POST /login
post_data = urllib.parse.urlencode({
    'username': 'admin',
    'password': 'Admin@123',
    'csrf_token': csrf_token
}).encode('utf-8')

req = urllib.request.Request('http://127.0.0.1:5000/login', data=post_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
resp = opener.open(req)
print('Login URL:', resp.geturl())

# 3. GET /settings
settings_html = opener.open('http://127.0.0.1:5000/settings').read().decode('utf-8')
print('Settings page size:', len(settings_html))
for line in settings_html.splitlines():
    if 'MySQL' in line or 'Connected' in line or 'Amazon S3' in line:
        print('Settings snippet:', line.strip())

# 4. GET /students
students_html = opener.open('http://127.0.0.1:5000/students').read().decode('utf-8')
print('Students page size:', len(students_html))
if '22MIS0293' in students_html:
    print('VERIFIED: Student 22MIS0293 appears on Cloud Students list!')
