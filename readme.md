# Mastodon Admin Metrics

> This is a bit WIP, I'm still figuring out the format of metrics and how to provide them consistently

This is a very simple script that exports mastodon admin dashboard metrics ("measures") to prometheus format,
to allow for easier manipulation and dashboard integration into grafana and the likes.

I've made a recommended grafana dashboard to go along with this data source: `WIP`

To make it work, go to "development" in the mastodon web UI, and create an application with the permissions `read` and `admin:read`,
feel free to disable all other permissions (such as `write`).

- `MASTODON_BASE_URL`: Your server's web interface URL, stripped down to `/`, basically the domain/url that you access your server with.
- `MASTODON_CLIENT_KEY`: The application's "Client ID", or Client Key
- `MASTODON_CLIENT_SECRET`: The application's Client Secret
- `MASTODON_ACCESS_TOKEN`: The application's Access Token
- `PORT`: The port that the metrics server will bind itself to, defaults to `9876`

There's also a Dockerfile provided, so that you could add it to a `docker-compose.yml` file with the following snippet:
```yaml
# ...

    masto_admin_metrics:
        build: masto_admin_metrics
        environment:
            MASTODON_BASE_URL: "https://your.server"
            MASTODON_CLIENT_KEY: KEY
            MASTODON_CLIENT_SECRET: SECRET
            MASTODON_ACCESS_TOKEN: TOKEN
        restart: always
        ports:
        - "127.0.0.1:9876:9876"
```