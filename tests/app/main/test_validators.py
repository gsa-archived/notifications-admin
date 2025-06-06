from unittest.mock import Mock

import pytest
from wtforms import ValidationError

from app.main.validators import (
    MustContainAlphanumericCharacters,
    NoCommasInPlaceHolders,
    OnlySMSCharacters,
    ValidGovEmail,
)


def _gen_mock_field(x):
    return Mock(data=x)


@pytest.mark.parametrize(
    "email",
    [  # TODO: update with email_domains.txt
        "test@gsa.gov",
        "test@abc.gov",
        "test@xyz.gov",
    ],
)
def test_valid_list_of_white_list_email_domains(
    client_request,
    email,
):
    email_domain_validators = ValidGovEmail()
    email_domain_validators(None, _gen_mock_field(email))


@pytest.mark.parametrize(
    "email",
    [  # TODO: update with email_domains.txt
        "test@gov.gsa",
        "test@gmail.co",
        "test@mail.co",
        "test@amazonses.co",
        "test@amazon.com",
    ],
)
def test_invalid_list_of_white_list_email_domains(
    client_request,
    email,
    mock_get_organizations,
):
    email_domain_validators = ValidGovEmail()
    with pytest.raises(ValidationError):
        email_domain_validators(None, _gen_mock_field(email))


def test_for_commas_in_placeholders(
    client_request,
):
    with pytest.raises(ValidationError) as error:
        NoCommasInPlaceHolders()(None, _gen_mock_field("Hello ((name,date))"))
    assert str(error.value) == "You cannot put commas between double parenthesis"
    NoCommasInPlaceHolders()(None, _gen_mock_field("Hello ((name))"))


@pytest.mark.parametrize("msg", ["The quick brown fox", "Thé “quick” bröwn fox\u200b"])
def test_sms_character_validation(client_request, msg):
    OnlySMSCharacters(template_type="sms")(None, _gen_mock_field(msg))


@pytest.mark.parametrize(
    ("data", "err_msg"),
    [
        (
            "∆ abc 📲 def 📵 ghi",
            (
                "Please remove the unaccepted character ∆, 📲 and 📵 in your message, then save again"
            ),
        ),
        (
            "📵",
            (
                "Please remove the unaccepted character 📵 in your message, then save again"
            ),
        ),
    ],
)
def test_non_sms_character_validation(data, err_msg, client_request):
    with pytest.raises(ValidationError) as error:
        OnlySMSCharacters(template_type="sms")(None, _gen_mock_field(data))

    assert str(error.value) == err_msg


@pytest.mark.parametrize("string", [".", "A.", ".8...."])
def test_if_string_does_not_contain_alphanumeric_characters_raises(string):
    with pytest.raises(ValidationError) as error:
        MustContainAlphanumericCharacters()(None, _gen_mock_field(string))

    assert str(error.value) == "Must include at least two alphanumeric characters"


@pytest.mark.parametrize("string", [".A8", "AB.", ".42...."])
def test_if_string_contains_alphanumeric_characters_does_not_raise(string):
    MustContainAlphanumericCharacters()(None, _gen_mock_field(string))
