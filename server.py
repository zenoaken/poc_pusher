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


# users_status = {}
users_on_channel = {}
channels_per_user = {}
resources_per_user = {}


@app.route("/")
def hello():
    return "Agent Presence Test Server"


def get_users_on_channel(channel):
    if not users_on_channel.get(channel):
        users_on_channel[channel] = {}
    return users_on_channel[channel]


def get_user_on_channel(channel, username):
    if not get_users_on_channel(channel).get(username):
        get_users_on_channel(channel)[username] = {}
    return get_users_on_channel(channel)[username]


def get_channels_per_user(username):
    if not channels_per_user.get(username):
        channels_per_user[username] = {}
    return channels_per_user[username]


def get_channel_per_user(username, channel):
    if not get_channels_per_user(username).get(channel):
        get_channels_per_user(username)[channel] = {}
    return get_channels_per_user(username)[channel]


def get_resources_per_user(username):
    if not resources_per_user.get(username):
        resources_per_user[username] = {}
    return resources_per_user[username]


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
    webhook = pusher_client.validate_webhook(
        key=request.headers.get('X-Pusher-Key'),
        signature=request.headers.get('X-Pusher-Signature'),
        body=request.data
    )

    if not webhook:
        return "ok"

    webhook_time_ms = webhook["time_ms"]
    for event in webhook["events"]:
        channel = event["channel"]
        user = event["user_id"]

        if channel.startswith("presence-user-on-product-"):
            product = channel.split("-")[-2]

            current_status = get_user_on_channel(product, user)

            # continue if we already have a most recent information
            if current_status and current_status["time_ms"] > webhook_time_ms:
                continue

            status = "available" if event["name"] == "member_added" else "offline" if event[
                                                                                       "name"] == "member_removed" else None

            if status:
                if status == "available":
                    current_status["name"] = user
                    current_status["status"] = status
                    current_status["time_ms"] = webhook_time_ms
                    get_users_on_channel(product)[user] = current_status
                    get_channels_per_user(user)[product] = current_status
                elif status == "offline":
                    get_users_on_channel(product).pop(user, None)
                    get_channels_per_user(user).pop(product, None)
                pusher_client.trigger("private-user-status-changed-on-%s" % product, 'client-status-changed',
                                      {'user': user, 'status': status})
        elif channel.startswith("presence-users-on-resource-"):
            resource_type, resource_id = channel.split("-")[4:6]
            resource_key = "%s_%s" % (resource_type, resource_id)

            if event["name"] == "member_added":
                get_resources_per_user(user)[resource_key] = {
                    "type": resource_type,
                    "id": resource_id,
                    "action": "viewing"
                }
            elif event["name"] == "member_removed":
                get_resources_per_user(user).pop(resource_key, None)

    return "ok"


@app.route("/api/hooks/client-events", methods=['POST'])
def client_events_webhook():
    webhook = pusher_client.validate_webhook(
        key=request.headers.get('X-Pusher-Key'),
        signature=request.headers.get('X-Pusher-Signature'),
        body=request.data
    )

    if not webhook:
        return "ok"

    webhook_time_ms = webhook["time_ms"]
    for event in webhook["events"]:
        channel = event["channel"]

        event_data = json.loads(event["data"])
        user = event_data["user"]

        if channel.startswith("private-user-status-changed-on-"):
            product = channel.split("-")[-1]
            status = event_data["status"]

            current_status = get_user_on_channel(product, user)

            # continue if we already have a most recent information
            if not current_status or current_status["time_ms"] > webhook_time_ms:
                continue

            current_status["status"] = status
            current_status["time_ms"] = webhook_time_ms
        elif channel.startswith("presence-users-on-resource-"):
            resource_type, resource_id = channel.split("-")[4:6]
            resource_key = "%s_%s" % (resource_type, resource_id)

            if get_resources_per_user(user).get(resource_key):
                get_resources_per_user(user)[resource_key]["action"] = event["event"].split("-")[-1]

    return "ok"


@app.route("/api/users")
def users():
    return jsonify(channels_per_user)


@app.route("/api/user/<username>/resources")
def resources_user(username):
    return jsonify(
        filter(
            lambda resource: resource["type"] == request.args.get('type'),
            get_resources_per_user(username).values()
        ) if request.args.get('type') else get_resources_per_user(username).values()
    )


@app.route("/api/user/<username>")
def user(username):
    return jsonify(get_channels_per_user(username))


# @app.route("/api/resources")
# def resources_in_use():
#     return jsonify(resources_per_user.keys())
#
#
# @app.route("/api/resource/<type>/<id>/presence")
# def users_in_resource():
#     raise NotImplementedError


@app.route("/api/channel/<channel>/users")
def user_in_channel(channel):
    return jsonify(
        filter(
            lambda user: user["status"] == request.args.get("status"),
            get_users_on_channel(channel).values()
        ) if request.args.get("status") else get_users_on_channel(channel).values()
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=environ.get("PORT", 5000))
