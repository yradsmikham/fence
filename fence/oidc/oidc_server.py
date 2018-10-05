from authlib.common.urls import urlparse, url_decode
from authlib.flask.oauth2 import AuthorizationServer
from authlib.specs.rfc6749.authenticate_client import (
    ClientAuthentication as AuthlibClientAuthentication,
)
from authlib.specs.rfc6749.errors import InvalidClientError as AuthlibClientError
import flask
from flask import Response, json
from flask import request as flask_req
from authlib.specs.rfc6749 import OAuth2Request
import urllib

from fence.oidc.errors import InvalidClientError
from fence.oidc.jwt_generator import generate_token


class ClientAuthentication(AuthlibClientAuthentication):
    """
    For authlib implementation---this class is a callable that goes on the OIDC server
    in order to authenticate OAuth clients.
    """

    def authenticate(self, request, methods):
        """
        Override method from authlib
        """
        client = super(ClientAuthentication, self).authenticate(request, methods)
        # don't allow confidential clients to not use auth
        if client.is_confidential:
            m = list(methods)
            if "none" in m:
                m.remove("none")
            try:
                client = super(ClientAuthentication, self).authenticate(request, m)
            except AuthlibClientError:
                raise InvalidClientError(
                    "OAuth client failed to authenticate; client ID or secret is"
                    " missing or incorrect"
                )
        return client


class OIDCServer(AuthorizationServer):
    """
    Implement the OIDC provider to attach to the flask app.

    Specific OAuth grants (authorization code, refresh token) are added on to
    a server instance using ``OIDCServer.register_grant_endpoint(grant)``. For
    usage, see ``fence/oidc/server.py``.

    NOTE: As of Authlib==0.9 there is a bug with percent encoding spaces
          See https://github.com/lepture/authlib/issues/93

          As a temporary workaround until it is patched in authlib, we are overriding
          some methods and modifying the `.url` of the request to make sure that
          spaces are percent encoded.
    """

    def init_app(self, app, query_client=None, save_token=None):
        if query_client is not None:
            self.query_client = query_client
        if save_token is not None:
            self.save_token = save_token
        self.app = app
        self.generate_token = generate_token
        self.init_jwt_config(app)
        if getattr(self, "query_client"):
            self.authenticate_client = ClientAuthentication(query_client)

    def validate_consent_request(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        kwargs["request"] = _ensure_spaces_percent_encoded(request)
        return super(OIDCServer, self).validate_consent_request(*args, **kwargs)

    def create_token_response(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        kwargs["request"] = _ensure_spaces_percent_encoded(request)
        return super(OIDCServer, self).create_token_response(*args, **kwargs)

    def create_endpoint_response(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        kwargs["request"] = _ensure_spaces_percent_encoded(request)
        return super(OIDCServer, self).create_endpoint_response(*args, **kwargs)


def _ensure_spaces_percent_encoded(request):
    q = request or flask_req
    q.url = q.url.replace(" ", "%20")
    return q
