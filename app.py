import requests
from flask import Flask, request, redirect, url_for, render_template, Response
import os
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)


PORT = int(os.getenv('PORT', 8080))
REAL_URL = os.getenv('REAL_URL', 'https://google.ru')
PASSWORD = os.getenv('PASSWORD', '1234')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8051')
AUTH_COOKIE_NAME = 'auth'

@app.before_request
def check_authentication_and_serve_login():
    if request.path == '/login' and request.method == 'POST':
        return None 

    if request.cookies.get(AUTH_COOKIE_NAME) != PASSWORD:
        return render_template('login.html')
    
    return None 

@app.route('/login', methods=['POST'])
def handle_login_post():
    submitted_password = request.form.get('password')
    if submitted_password == PASSWORD:
        resp = redirect(url_for('proxy_all')) 
        resp.set_cookie(AUTH_COOKIE_NAME, PASSWORD, httponly=True, samesite='Strict')
        return resp
    else:
        return render_template('wrongPassword.html')

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def proxy_all(path):
    target_url = f"{REAL_URL}/{path}"
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"

    headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'connection', 'content-length', 'cookie']}
    data = request.get_data()

    try:
        proxied_response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=data,
            allow_redirects=False, 
            stream=True
        )
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error proxying request to {target_url}: {e}")
        return Response("Proxy Error: Could not reach the upstream server.", status=500)

    response = Response(
        proxied_response.iter_content(chunk_size=4096), 
        status=proxied_response.status_code
    )
    
    excluded_resp_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    for key, value in proxied_response.headers.items():
        if key.lower() not in excluded_resp_headers:
            if key.lower() == 'location':

                rewritten_location = value.replace(REAL_URL, PUBLIC_BASE_URL)
                response.headers[key] = rewritten_location
            else:
                response.headers[key] = value

    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)

