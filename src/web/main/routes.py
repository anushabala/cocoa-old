__author__ = 'anushabala'

import uuid
from datetime import datetime
import time

from flask import jsonify, render_template, request, redirect, url_for, Markup

from flask import current_app as app

from . import main
from src.web.main.web_utils import get_backend
from src.web.main.backend_utils import Status
from src.basic.event import Event


def generate_userid():
    return "U_" + uuid.uuid4().hex


def userid():
    return request.args.get('uid')


def userid_prefix():
    return userid()[:6]


def generate_unique_key():
    return str(uuid.uuid4().hex)


def format_message(message, status_message):
    timestamp = datetime.now().strftime('%x %X')
    left_delim = "<" if status_message else ""
    right_delim = ">" if status_message else ""
    return "[{}] {}{}{}".format(timestamp, left_delim, message, right_delim)


# Required args: uid (the user ID of the current user)
@main.route('/_connect/', methods=['GET'])
def connect():
    backend = get_backend()
    backend.connect(userid())
    return jsonify(success=True)


# Required args: uid (the user ID of the current user)
@main.route('/_disconnect/', methods=['GET'])
def disconnect():
    backend = get_backend()
    backend.disconnect(userid())
    return jsonify(success=True)


# Required args: uid (the user ID of the current user)
@main.route('/_check_chat_valid/', methods=['GET'])
def is_chat_valid():
    backend = get_backend()
    if backend.is_chat_valid(userid()):
        return jsonify(valid=True)
    else:
        return jsonify(valid=False, message=backend.get_user_message(userid()))


@main.route('/_submit_survey/', methods=['POST'])
def submit_survey():
    backend = get_backend()
    data = request.json['response']
    uid = request.json['uid']
    backend.submit_survey(uid, data)
    return jsonify(success=True)


@main.route('/_check_inbox/', methods=['GET'])
def check_inbox():
    backend = get_backend()
    uid = userid()
    event = backend.receive(uid)
    if event is not None:
        message = None
        if event.action == 'message':
            message = format_message("Partner: {}".format(event.data), False)
        elif event.action == 'join':
            message = format_message("Your partner has joined the room.", True)
        elif event.action == 'leave':
            message = format_message("Your partner has left the room.", True)
        elif event.action == 'select':
            ordered_item = backend.schema.get_ordered_item(event.data)
            message = format_message("Your partner selected: {}".format(", ".join([v[1] for v in ordered_item])),
                                     True)
        elif event.action == 'offer':
            message = format_message("Your partner offered: $%d" % event.data, True)
        elif event.action == 'typing':
            if event.data == 'started':
                message = "Your partner is typing..."
            else:
                message = ""
            return jsonify(message=message, status=True, received=True)
        return jsonify(message=message, status=False, received=True)
    return jsonify(status=False, received=False)


@main.route('/_typing_event/', methods=['GET'])
def typing_event():
    backend = get_backend()
    action = request.args.get('action')

    uid = userid()
    chat_info = backend.get_chat_info(uid)
    backend.send(uid,
                 Event.TypingEvent(chat_info.agent_index,
                                   action,
                                   str(time.time())))

    return jsonify(success=True)


@main.route('/_send_message/', methods=['GET'])
def text():
    backend = get_backend()
    message = request.args.get('message')
    displayed_message = format_message("You: {}".format(message), False)
    uid = userid()
    time_taken = float(request.args.get('time_taken'))
    received_time = time.time()
    start_time = received_time - time_taken
    chat_info = backend.get_chat_info(uid)
    backend.send(uid,
                 Event.MessageEvent(chat_info.agent_index,
                                    message,
                                    str(received_time),
                                    str(start_time))
                 )
    return jsonify(message=displayed_message)


@main.route('/_join_chat/', methods=['GET'])
def join_chat():
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    backend = get_backend()
    uid = userid()
    chat_info = backend.get_chat_info(uid)
    backend.send(uid, Event.JoinEvent(chat_info.agent_index,
                                      uid,
                                      str(time.time())))
    return jsonify(message=format_message("You entered the room.", True))


@main.route('/_leave_chat/', methods=['GET'])
def leave_chat():
    backend = get_backend()
    uid = userid()
    chat_info = backend.get_chat_info(uid)
    backend.send(uid, Event.LeaveEvent(chat_info.agent_index,
                                       uid,
                                       str(time.time())))
    return jsonify(success=True)


@main.route('/_check_status_change/', methods=['GET'])
def check_status_change():
    backend = get_backend()
    uid = userid()
    assumed_status = request.args.get('assumed_status')
    if backend.is_status_unchanged(uid, assumed_status):
        return jsonify(status_change=False)
    else:
        return jsonify(status_change=True)


@main.route('/index', methods=['GET', 'POST'])
@main.route('/', methods=['GET', 'POST'])
def index():
    """Chat room. The user's name and room must be stored in
    the session."""

    if not request.args.get('uid'):
        return redirect(url_for('main.index', uid=generate_userid(), **request.args))

    backend = get_backend()

    backend.create_user_if_not_exists(userid())

    status = backend.get_updated_status(userid())

    mturk = True if request.args.get('mturk') and int(request.args.get('mturk')) == 1 else None
    if status == Status.Waiting:
        waiting_info = backend.get_waiting_info(userid())
        return render_template('waiting.html',
                               seconds_until_expiration=waiting_info.num_seconds,
                               waiting_message=waiting_info.message,
                               uid=userid(),
                               title=app.config['task_title'],
                               icon=app.config['task_icon'])
    elif status == Status.Finished:
        finished_info = backend.get_finished_info(userid(), from_mturk=mturk)
        mturk_code = finished_info.mturk_code if mturk else None
        visualize_link = False
        if request.args.get('debug') is not None and request.args.get('debug') == '1':
            visualize_link = True
        return render_template('finished.html',
                               finished_message=finished_info.message,
                               mturk_code=mturk_code,
                               title=app.config['task_title'],
                               icon=app.config['task_icon'],
                               visualize=visualize_link,
                               uid=userid())
    elif status == Status.Chat:
        peek = False
        if request.args.get('peek') is not None and request.args.get('peek') == '1':
            peek = True
        chat_info = backend.get_chat_info(userid(), peek=peek)
        partner_kb = None
        if peek:
            partner_kb = chat_info.partner_kb.to_dict()
        return render_template('chat.html',
                               uid=userid(),
                               kb=chat_info.kb.to_dict(),
                               attributes=[attr.name for attr in chat_info.attributes],
                               num_seconds=chat_info.num_seconds,
                               title=app.config['task_title'],
                               instructions=Markup(app.config['instructions']),
                               icon=app.config['task_icon'],
                               partner_kb=partner_kb,
                               quit_enabled=app.config['user_params']['skip_chat_enabled'],
                               quit_after=app.config['user_params']['status_params']['chat']['num_seconds'] -
                                          app.config['user_params']['quit_after'])
    elif status == Status.Survey:
        survey_info = backend.get_survey_info(userid())
        return render_template('task_survey.html',
                               title=app.config['task_title'],
                               uid=userid(),
                               icon=app.config['task_icon'],
                               kb=survey_info.kb.to_dict(),
                               partner_kb=survey_info.partner_kb.to_dict(),
                               attributes=[attr.name for attr in survey_info.attributes],
                               message=survey_info.message)


@main.route('/visualize', methods=['GET', 'POST'])
def visualize():
    uid = request.args.get('uid')
    backend = get_backend()
    html_lines = ['<head><style>table{ table-layout: fixed; width: 600px; border-collapse: collapse; } '
                  'tr:nth-child(n) { border: solid thin;}</style></head><body>']
    html_lines.extend(backend.visualize_chat(uid))
    html_lines.append('</body>')
    html_lines = "".join(html_lines)
    return render_template('visualize.html',
                           dialogue=Markup(html_lines))


@main.route('/_select_option/', methods=['GET'])
def select():
    backend = get_backend()
    selection_id = int(request.args.get('selection'))
    if selection_id == -1:
        return
    selected_item = backend.select(userid(), selection_id)

    ordered_item = backend.schema.get_ordered_item(selected_item)
    displayed_message = format_message("You selected: {}".format(", ".join([v[1] for v in ordered_item])), True)
    return jsonify(message=displayed_message)


@main.route('/_offer/', methods=['GET'])
def offer():
    backend = get_backend()
    offer = float(request.args.get('offer'))
    if offer == -1:
        return
    backend.make_offer(userid(), offer)

    displayed_message = format_message("You proposed: $%d" % offer, True)
    return jsonify(message=displayed_message)
