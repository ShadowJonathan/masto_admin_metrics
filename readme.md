# Mastodon Admin Metrics

This is a very simple script that exports mastodon admin dashboard metrics ("measures") to prometheus format,
to allow for easier manipulation and dashboard integration into grafana and the likes.

To make it work, go to "development" in the mastodon web UI, and create an application with the permissions `read` and `admin:read`,
feel free to disable all other permissions (such as `write`).

- `MASTODON_BASE_URL`: Your server's web interface URL, stripped down to `/`, basically the domain/url that you access your server with.
- `MASTODON_CLIENT_KEY`: The application's "Client ID", or Client Key
- `MASTODON_CLIENT_SECRET`: The application's Client Secret
- `MASTODON_ACCESS_TOKEN`: The application's Access Token
- `PORT`: The port that the metrics server will bind itself to, defaults to `9876`