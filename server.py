import pusher
from flask import Flask, request, jsonify
from flask_cors import CORS
from os import environ
import json

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

pusher_client = pusher.Pusher(
  app_id='341057',
  key='ab8cf6e917558807f315',
  secret='7d9f17ff32a4d4b2a773',
  cluster='eu',
  ssl=True
)

users_status = {}

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/api/pusher/auth", methods=['POST'])
def pusher_auth():
    user_name = request.environ['HTTP_X_CSRF_TOKEN']
    auth = pusher_client.authenticate(
        channel=request.form['channel_name'],
        socket_id=request.form['socket_id'],
        custom_data={
            u'user_id': user_name,
            u'user_info': {
                u'name': user_name
            }
        }
    )
    response = jsonify(auth)
    return response


@app.route("/api/hooks/presence", methods=['POST'])
def presence_webhook():
    global users_status

    webhook = pusher_client.validate_webhook(
        key=request.headers.get('X-Pusher-Key'),
        signature=request.headers.get('X-Pusher-Signature'),
        body=request.data
    )

    webhook_time_ms = webhook["time_ms"]
    for event in webhook["events"]:
        channel = event["channel"]
        if channel.startswith("presence-user-"):
            user = channel.split("-")[2]
            current_user_status = users_status.get(user, {"status": "unknown", "time_ms": 0})

            # continue if we already have a most recent information
            if current_user_status["time_ms"] > webhook_time_ms:
                continue

            status = "online" if event["name"] == "member_added" else "offline" if event["name"] == "member_removed" else None

            if status:
                users_status[user] = {"status": status, "time_ms": webhook_time_ms}
                pusher_client.trigger('private-user-status-changed', 'client-status-changed',
                                      {'user': user, 'status': status})
        elif channel.startswith("presence-users-on-ticket-"):
            # TODO build inverted index resources being used by user
            pass

    return "ok"


@app.route("/api/hooks/client-events", methods=['POST'])
def client_events_webhook():
    global users_status

    webhook = pusher_client.validate_webhook(
        key=request.headers.get('X-Pusher-Key'),
        signature=request.headers.get('X-Pusher-Signature'),
        body=request.data
    )

    webhook_time_ms = webhook["time_ms"]
    for event in webhook["events"]:
        channel = event["channel"]
        if channel == "private-user-status-changed":
            event_data = json.loads(event["data"])
            user = event_data["user"]
            status = event_data["status"]
            current_user_status = users_status.get(user, {"status": "unknown", "time_ms": 0})

            # continue if we already have a most recent information
            if current_user_status["time_ms"] > webhook_time_ms:
                continue

            users_status[user] = {"status": status, "time_ms": webhook_time_ms}
        elif channel.startswith("presence-users-on-ticket-"):
            # TODO set user state on resource (e.g. viewing, typing)
            pass

    return "ok"


@app.route("/api/users")
def users():
    return jsonify(users_status)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=environ.get("PORT", 5000))
