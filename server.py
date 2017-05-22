import pusher
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

pusher_client = pusher.Pusher(
  app_id='341057',
  key='ab8cf6e917558807f315',
  secret='7d9f17ff32a4d4b2a773',
  cluster='eu',
  ssl=True
)

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/api/pusher/auth", methods=['POST'])
def pusher_auth():
    auth = pusher_client.authenticate(
        channel=request.form['channel_name'],
        socket_id=request.form['socket_id'],
        custom_data={
            u'user_id': request.form['socket_id'],
            u'user_info': {
                u'name': request.environ['HTTP_X_CSRF_TOKEN']
            }
        }
    )
    response = jsonify(auth)
    # response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
