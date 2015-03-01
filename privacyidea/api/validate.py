# -*- coding: utf-8 -*-
#
# http://www.privacyidea.org
# (c) cornelius kölbel, privacyidea.org
#
# 2014-12-08 Cornelius Kölbel, <cornelius@privacyidea.org>
#            Complete rewrite during flask migration
#            Try to provide REST API
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
# License as published by the Free Software Foundation; either
# version 3 of the License, or any later version.
#
# This code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU AFFERO GENERAL PUBLIC LICENSE for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

__doc__ = """This module contains the REST API for doing authentication.
The methods are tested in the file tests/test_api_validate.py
"""
from flask import (Blueprint, request, g, current_app)
from privacyidea.lib.user import get_user_from_param
from lib.utils import send_result, getParam
from ..lib.decorators import (check_user_or_serial_in_request)
from lib.utils import required
from privacyidea.lib.token import (check_user_pass, check_serial_pass)
from privacyidea.api.lib.utils import remove_session_from_param
from privacyidea.lib.audit import getAudit
from privacyidea.api.lib.prepolicy import (prepolicy, set_realm)
from privacyidea.api.lib.postpolicy import (postpolicy,
                                            check_tokentype, check_serial,
                                            no_detail_on_fail,
                                            no_detail_on_success)
from privacyidea.lib.policy import PolicyClass
import logging
log = logging.getLogger(__name__)

validate_blueprint = Blueprint('validate_blueprint', __name__)


@validate_blueprint.before_request
def before_request():
    """
    This is executed before the request
    """
    request.all_data = remove_session_from_param(request.values, request.data)
    # Create a policy_object, that reads the database audit settings
    # and contains the complete policy definition during the request.
    # This audit_object can be used in the postpolicy and prepolicy and it
    # can be passed to the innerpolicies.
    g.policy_object = PolicyClass()
    g.audit_object = getAudit(current_app.config)
    g.audit_object.log({"success": False,
                        "action_detail": "",
                        "client": request.remote_addr,
                        "client_user_agent": request.user_agent.browser,
                        "privcyidea_server": request.host,
                        "action": "%s %s" % (request.method, request.url_rule),
                        "info": ""})


@validate_blueprint.after_request
def after_request(response):
    """
    This function is called after a request
    :return: The response
    """
    # In certain error cases the before_request was not handled
    # completely so that we do not have an audit_object
    if "audit_object" in g:
        g.audit_object.finalize_log()

    # No caching!
    response.headers['Cache-Control'] = 'no-cache'
    return response


@validate_blueprint.route('/check', methods=['POST', 'GET'])
@postpolicy(no_detail_on_fail, request=request)
@postpolicy(no_detail_on_success, request=request)
@postpolicy(check_tokentype, request=request)
@postpolicy(check_serial, request=request)
@prepolicy(set_realm, request=request)
@check_user_or_serial_in_request
def check():
    """
    check the authentication for a user or a serial number.
    Either a ``serial`` or a ``user`` is required to authenticate.
    The PIN and OTP value is sent in the parameter ``pass``.

    :param serial: The serial number of the token, that tries to authenticate.
    :param user: The loginname/username of the user, who tries to authenticate.
    :param realm: The realm of the user, who tries to authenticate. If the
        realm is omitted, the user is looked up in the default realm.
    :param pass: The password, that consists of the OTP PIN and the OTP value.

    :return: a json result with a boolean "result": true

    **Example response** for a successful authentication:

       .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json

            {
              "detail": {
                "message": "matching 1 tokens",
                "serial": "PISP0000AB00",
                "type": "spass"
              },
              "id": 1,
              "jsonrpc": "2.0",
              "result": {
                "status": true,
                "value": true
              },
              "version": "privacyIDEA unknown"
            }
    """
    user = get_user_from_param(request.all_data)
    serial = getParam(request.all_data, "serial")
    password = getParam(request.all_data, "pass", required)
    options = {"g": g,
               "clientip": request.remote_addr}
    if serial:
        result, details = check_serial_pass(serial, password, options=options)
    else:
        result, details = check_user_pass(user, password, options=options)

    g.audit_object.log({"info": details.get("message"),
                        "success": result,
                        "serial": serial or details.get("serial"),
                        "tokentype": details.get("type"),
                        "user": user.login,
                        "realm": user.realm})
    return send_result(result, details=details)


@validate_blueprint.route('/simplecheck', methods=['POST', 'GET'])
@check_user_or_serial_in_request
def simplecheck():
    """
    check the authentication for a user or a serial number.
    Either a ``serial`` or a ``user`` is required to authenticate.
    The PIN and OTP value is sent in the parameter ``pass``.

    TODO: This API call does not honour the policies AUTHZ:tokentype and
    AUTHZ:serial!

    :param serial: The serial number of the token, that tries to authenticate.
    :param user: The loginname/username of the user, who tries to authenticate.
    :param realm: The realm of the user, who tries to authenticate. If the
        realm is omitted, the user is looked up in the default realm.
    :param pass: The password, that consists of the OTP PIN and the OTP value.

    :return: a json result with a boolean "result": true

    **Example response** for a succesful authentication:

       .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/text

           :-)
    """
    user = get_user_from_param(request.all_data)
    serial = getParam(request.all_data, "serial")
    password = getParam(request.all_data, "pass", required)
    log.warning("Deprecation Warning: simplecheck will be removed in version "
                "2.2! Do not use it anymore")
    if serial:
        result, details = check_serial_pass(serial, password)
    else:
        result, details = check_user_pass(user, password)

    if result is True:
        ret = ":-)"
    else:
        ret = ":-("

    g.audit_object.log({"info": details.get("message"),
                        "success": result,
                        "serial": serial or details.get("serial"),
                        "tokentype": details.get("type"),
                        "user": user.login,
                        "realm": user.realm})
    return ret


@validate_blueprint.route('/samlcheck', methods=['POST', 'GET'])
@postpolicy(check_tokentype, request=request)
@postpolicy(check_serial, request=request)
def samlcheck():
    raise NotImplementedError("samlcheck is not implemented, yet")
