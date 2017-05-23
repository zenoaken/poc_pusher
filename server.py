import pusher
from flask import Flask, request, jsonify
from flask_cors import CORS
from os import environ
import json
from collections import defaultdict

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


def get_user_status(username):
    return users_status.get(username, {"name": username, "status": "unknown", "time_ms": 0})


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
        user = event["user_id"]
        current_user_status = get_user_status(user)

        if channel.startswith("presence-user-"):
            # continue if we already have a most recent information
            if current_user_status["time_ms"] > webhook_time_ms:
                continue

            status = "online" if event["name"] == "member_added" else "offline" if event[
                                                                                       "name"] == "member_removed" else None

            if status:
                if status == "online":
                    current_user_status["status"] = status
                    current_user_status["time_ms"] = webhook_time_ms
                    users_status[user] = current_user_status
                elif status == "offline":
                    users_status.pop(user)
                pusher_client.trigger('private-user-status-changed', 'client-status-changed',
                                      {'user': user, 'status': status})
        elif channel.startswith("presence-users-on-resource-"):
            resource_type, resource_id = channel.split("-")[4:6]
            resource_key = "%s_%s" % (resource_type, resource_id)

            if event["name"] == "member_added":
                current_user_status[resource_key] = {
                    "type": resource_type,
                    "id": resource_id,
                    "action": "viewing"
                }
            elif event["name"] == "member_removed":
                current_user_status.pop(resource_key)

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
        elif channel.startswith("presence-users-on-resource-"):
            # TODO set user state on resource (e.g. viewing, typing)
            resource_type, resource_id = channel.split("-")[4:6]
            resource_key = "%s_%s" % (resource_type, resource_id)

            if current_user_status[resource_key]:
                current_user_status[resource_key]["action"] = event["name"].split("-")[-1]

    return "ok"


@app.route("/api/users")
def users():
    return jsonify(users_status.values())


@app.route("/api/user/<username>/resources")
def user_resources(username):
    return jsonify(users_status.get(username, {}).get("resources", {}).values())

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=environ.get("PORT", 5000))
