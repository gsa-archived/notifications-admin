import os
import time
import uuid

import jwt
import requests
from flask import (
    Markup,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from notifications_utils.url_safe_token import generate_token

from app import login_manager, user_api_client
from app.main import main
from app.main.forms import LoginForm
from app.main.views.index import error
from app.main.views.verify import activate_user
from app.models.user import InvitedUser, User
from app.utils import hide_from_search_engines
from app.utils.login import is_safe_redirect_url
from app.utils.time import is_less_than_days_ago


def _reformat_keystring(orig):
    new_keystring = orig.replace("-----BEGIN PRIVATE KEY-----", "")
    new_keystring = new_keystring.replace("-----END PRIVATE KEY-----", "")
    new_keystring = new_keystring.strip()
    new_keystring = new_keystring.replace(" ", "\n")
    new_keystring = "\n".join(
        ["-----BEGIN PRIVATE KEY-----", new_keystring, "-----END PRIVATE KEY-----"]
    )
    new_keystring = f"{new_keystring}\n"
    return new_keystring


def _get_access_token(code, state):
    client_id = os.getenv("LOGIN_DOT_GOV_CLIENT_ID")
    access_token_url = os.getenv("LOGIN_DOT_GOV_ACCESS_TOKEN_URL")
    keystring = os.getenv("LOGIN_PEM")
    if " " in keystring:
        keystring = _reformat_keystring(keystring)

    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": access_token_url,
        "jti": str(uuid.uuid4()),
        # JWT expiration time (10 minute maximum)
        "exp": int(time.time()) + (10 * 60),
    }
    token = jwt.encode(payload, keystring, algorithm="RS256")
    base_url = f"{access_token_url}?"
    cli_assert = f"client_assertion={token}"
    cli_assert_type = "client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer"
    code_param = f"code={code}"
    url = f"{base_url}{cli_assert}&{cli_assert_type}&{code_param}&grant_type=authorization_code"
    headers = {"Authorization": "Bearer %s" % token}
    response = requests.post(url, headers=headers)
    if response.json().get("access_token") is None:
        # Capture the response json here so it hopefully shows up in error reports
        current_app.logger.error(f"Error when getting access token {response.json()}")
        raise KeyError(f"'access_token' {response.json()}")
    access_token = response.json()["access_token"]
    return access_token


def _get_user_email_and_uuid(access_token):
    headers = {"Authorization": "Bearer %s" % access_token}
    user_info_url = os.getenv("LOGIN_DOT_GOV_USER_INFO_URL")
    user_attributes = requests.get(
        user_info_url,
        headers=headers,
    )
    user_email = user_attributes.json()["email"]
    user_uuid = user_attributes.json()["sub"]
    return user_email, user_uuid


def _do_login_dot_gov():
    # start login.gov
    code = request.args.get("code")
    state = request.args.get("state")
    login_gov_error = request.args.get("error")

    if login_gov_error:
        current_app.logger.error(f"login.gov error: {login_gov_error}")
        raise Exception(f"Could not login with login.gov {login_gov_error}")
    elif code and state:

        # activate the user
        try:
            access_token = _get_access_token(code, state)
            user_email, user_uuid = _get_user_email_and_uuid(access_token)
            redirect_url = request.args.get("next")
            user = user_api_client.get_user_by_uuid_or_email(user_uuid, user_email)

            # Check if the email needs to be revalidated
            is_fresh_email = is_less_than_days_ago(
                user["email_access_validated_at"], 90
            )
            if not is_fresh_email:
                return verify_email(user, redirect_url)

            usr = User.from_email_address(user["email_address"])
            activate_user(usr.id)
        except BaseException as be:  # noqa B036
            current_app.logger.error(be)
            error(401)
        return redirect(url_for("main.show_accounts_or_dashboard", next=redirect_url))

    # end login.gov


def verify_email(user, redirect_url):
    user_api_client.send_verify_code(user["id"], "email", None, redirect_url)
    title = "Email resent" if request.args.get("email_resent") else "Check your email"
    redirect_url = request.args.get("next")
    return render_template(
        "views/re-validate-email-sent.html", title=title, redirect_url=redirect_url
    )


@main.route("/sign-in", methods=(["GET", "POST"]))
@hide_from_search_engines
def sign_in():

    if os.getenv("NOTIFY_E2E_TEST_EMAIL"):
        current_app.logger.warning("E2E TESTS ARE ENABLED.")
        current_app.logger.warning(
            "If you are getting a 404 on signin, comment out E2E vars in .env file!"
        )
        user = user_api_client.get_user_by_email(os.getenv("NOTIFY_E2E_TEST_EMAIL"))
        activate_user(user["id"])
        return redirect(url_for("main.show_accounts_or_dashboard"))

    # If we have to revalidated the email, send the message
    # via email and redirect to the "verify your email page"
    # and don't proceed further with login

    email_verify_template = _do_login_dot_gov()
    if (
        email_verify_template
        and not isinstance(email_verify_template, Response)
        and "Check your email" in email_verify_template
    ):
        return email_verify_template

    redirect_url = request.args.get("next")

    current_app.logger.warning("FAILED TO BOUNCE OUT OF SIGN IN")
    current_app.logger.info(f"current user is {current_user}")
    if current_user and current_user.is_authenticated:
        if redirect_url and is_safe_redirect_url(redirect_url):
            return redirect(redirect_url)
        return redirect(url_for("main.show_accounts_or_dashboard"))

    form = LoginForm()
    current_app.logger.info("Got the login form")
    password_reset_url = url_for(".forgot_password", next=request.args.get("next"))

    if form.validate_on_submit():
        user = User.from_email_address_and_password_or_none(
            form.email_address.data, form.password.data
        )

        if user:
            # add user to session to mark us as in the process of signing the user in
            session["user_details"] = {"email": user.email_address, "id": user.id}

            if user.state == "pending":
                return redirect(
                    url_for("main.resend_email_verification", next=redirect_url)
                )

            if user.is_active:
                if session.get("invited_user_id"):
                    invited_user = InvitedUser.from_session()
                    if user.email_address.lower() != invited_user.email_address.lower():
                        flash("You cannot accept an invite for another person.")
                        session.pop("invited_user_id", None)
                        abort(403)
                    else:
                        invited_user.accept_invite()

                user.send_login_code()

                if user.sms_auth:
                    return redirect(url_for(".two_factor_sms", next=redirect_url))

                if user.email_auth:
                    return redirect(
                        url_for(".two_factor_email_sent", next=redirect_url)
                    )

        # Vague error message for login in case of user not known, locked, inactive or password not verified
        flash(
            Markup(
                (
                    f"The email address or password you entered is incorrect."
                    f"&ensp;<a href={password_reset_url} class='usa-link'>Forgot your password?</a>"
                )
            )
        )

    other_device = current_user.logged_in_elsewhere()

    token = generate_token(
        str(request.remote_addr),
        current_app.config["SECRET_KEY"],
        current_app.config["DANGEROUS_SALT"],
    )
    url = os.getenv("LOGIN_DOT_GOV_INITIAL_SIGNIN_URL")
    # handle unit tests
    if url is not None:
        url = url.replace("NONCE", token)
        url = url.replace("STATE", token)
    return render_template(
        "views/signin.html",
        form=form,
        again=bool(redirect_url),
        other_device=other_device,
        password_reset_url=password_reset_url,
        initial_signin_url=url,
    )


@login_manager.unauthorized_handler
def sign_in_again():
    return redirect(url_for("main.sign_in", next=request.path))
