# -*- coding: utf-8 -*-
import json
import bot
import os
from app_factory import *
import json
from pprint import pprint
from flask import request, make_response, render_template, jsonify
import urlparse
import frichti_api

food_slacking_bot = bot.FoodSlackingBot()
slack = food_slacking_bot.client

app = create_app()


def _event_handler(event_type, slack_event):
    """
    A helper function that routes events from Slack to our Bot
    by event type and subtype.

    Parameters
    ----------
    event_type : str
        type of event recieved from Slack
    slack_event : dict
        JSON response from a Slack reaction event

    Returns
    ----------
    obj
        Response object with 200 - ok or 500 - No Event Handler error

    """
    team = slack_event["team_id"]
    food_slacking_bot.authToCorrectTeam(team)

    # ================ Message Events =============== #
    if event_type == "message":
        # Pass event to bot only if he is mentioned in the event's text
        if 'text' in slack_event['event'] and food_slacking_bot.getAtBot() in slack_event['event']['text']:
            channel = slack_event['event']['channel']
            message = slack_event['event']['text'].split(
                food_slacking_bot.getAtBot())[1].strip().lower()
            food_slacking_bot.handle_command(team, channel, message)
            return make_response("Food Slacking Bot handling command", 200,)

    # ============= Event Type Not Found! ============= #
    # If the event_type does not have a handler
    message = "You have not added an event handler for the %s" % event_type
    # Return a helpful error message
    return make_response(message, 200, {"X-Slack-No-Retry": 1})


@app.route("/install", methods=["GET"])
def pre_install():
    """This route renders the installation page with 'Add to Slack' button."""
    # Since we've set the client ID and scope on our Bot object, we can change
    # them more easily while we're developing our app.

    client_id = food_slacking_bot.oauth["client_id"]
    scope = food_slacking_bot.oauth["scope"]
    return render_template("install.html", client_id=client_id, scope=scope)


@app.route("/thanks", methods=["GET", "POST"])
def thanks():
    """
    This route is called by Slack after the user installs our app. It will
    exchange the temporary authorization code Slack sends for an OAuth token
    which we'll save on the bot object to use later.
    To let the user know what's happened it will also render a thank you page.
    """
    # Let's grab that temporary authorization code Slack's sent us from
    # the request's parameters.
    code_arg = request.args.get('code')
    # The bot's auth method to handles exchanging the code for an OAuth token
    food_slacking_bot.auth(code_arg)
    return render_template("thanks.html")


@app.route("/listening", methods=["GET", "POST"])
def hears():
    """
    This route listens for incoming events from Slack and uses the event
    handler helper function to route events to our Bot.
    """
    slack_event = json.loads(request.data)
    # ============= Slack URL Verification ============ #
    if "challenge" in slack_event:
        return make_response(slack_event["challenge"], 200, {"content_type":
                                                             "application/json"
                                                             })

    # ============ Slack Token Verification =========== #
    if os.environ.get("VERIFICATION_TOKEN") != slack_event.get("token"):
        message = "Invalid Slack verification token"
        # By adding "X-Slack-No-Retry" : 1 to our response headers, we turn off
        # Slack's automatic retries during development.
        make_response(message, 403, {"X-Slack-No-Retry": 1})

    # ====== Process Incoming Events from Slack ======= #
    if "event" in slack_event:
        event_type = slack_event["event"]["type"]
        return _event_handler(event_type, slack_event)

    return make_response("[NO EVENT IN SLACK REQUEST] These are not the droids\
                         you're looking for.", 404, {"X-Slack-No-Retry": 1})


@app.route('/reacts', methods=['GET', 'POST'])
def reacts():
    payload = json.loads(urlparse.parse_qs(request.get_data())['payload'][0])
    team_id = payload['team']['id']
    channel_id = payload['channel']['id']
    callback_id = payload['callback_id']
    actions = payload['actions']

    # Rethink this process
    if callback_id == 'food_provider_selection':
        food_provider_choice = actions[0]['value']
        response = food_slacking_bot.ask(food_provider_choice, 'menu_categories')
    elif callback_id == 'menu_category_selection':
        provider, category =   actions[0]['value'].split('/')
        response = food_slacking_bot.ask(provider, 'propositions', category)

    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True)