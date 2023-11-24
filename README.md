# External Membership Management System for SYN Shop

* https://membership.synshop.org (Production)
* https://membership-dev.synshop.org (Development)

## Introduction
When moving away from Drupal to a statically hosted website for https://synshop.org, the team realized that they would need to come up with a new solution for members to manage their Shop membership.  The Drupal implementation was written in PHP and connected to Stripe (our payment processor)

## The New System
The new system is written in Python / Flask, using Bootstrap 5 for the UI components.  It uses [Auth0](https://auth0.com) for user authentication and [Stripe](https://stripe.com) for the payment processing and subscription management.

## Setup for Development
This README assumes that you already have Stripe and Auth0 accounts set up and know how to use them.

To set up the development environment, you'll need to clone the git repository, create a Python (3.8+) virtual environment, and install its necessary dependencies as follows:

```bash
$ git clone git@github.com:synshop/membership.synshop.org.git
$ cd membership.synshop.org
$ python3 -m venv ./venv
$ . ./activate
$ pip install -r requirements.txt
```

### Encrypt Sensitive Properties
Once the environment has been created, you'll need to copy or rename the `config.py.default` file to `config.py` and encrypt some sensitive properties to be placed in the `config.py` file.  The three variables that need encrypting are the Flask session key (`ENCRYPTED_SESSION_KEY`), the Auth0 Client Secret (`ENCRYPTED_AUTH0_CLIENT_SECRET` and the Stripe API Token (`ENCRYPTED_STRIPE_TOKEN`)

You will use the built-in `encrypt` utility to do the encryption.  Be sure to use the same encryption key for each property

```bash
$ cd membership.synshop.org
$ . ./activate
$ cp config.py.default config.py
$ cd crypto
$ ./encrypt 
Please enter the encryption key: 
Please enter the plaintext you wish to encrypt: 
Encrypted Value: pdDNn2nVFDhlu/o8cdLfyg==
```
From here, take the `Encrypted Value` from above and add it to the `config.py` file.  For example:

```python
ENCRYPTED_AUTH0_CLIENT_SECRET="pdDNn2nVFDhlu/o8cdLfyg=="
```

### Add `ENCRYPTION_KEY` to your `~/.bashrc`
This is a matter of personal preference, but the `ENCRYPTION_KEY` environment variable needs to be added to some place that can be loaded into your environment, otherwise you'll have to enter it every time you restart the development server.

### Other `config.py` Properties
There are a few other `config.py` properties that need defining before you can start developing.  These properties, `STRIPE_PK`
and `PRICING_MAP` both change depending on whether you are developing or running a production system.  For development, the `STRIPE_PK` is the Stripe Public Key found in the Test environment and the `PRICING_MAP` is either set to either the development (`pricing_map_devo.yml`) or production (`pricing_map_prod.yml`) pricing map YAML file depending on which environment you are running.

### Run the Development Server
When developing locally, you'll need to make sure you use a DNS name that Auth0 can send a redirect to.  We use the Caddy HTTP server to proxy requests and handle the TLS termination, but you could technically use `http://localhost:8080` as long as you configure the callback for Auth0 to allow this.

To start the development server, activate the environment and run the `server.py` script:

```bash
$ cd membership.synshop.org
$ . ./activate
$ python server.py
```
You should see the following output

```python
(venv) $ python server.py 
[2023-10-25 17:55:02,533] INFO in server: -------------------------------------
[2023-10-25 17:55:02,533] INFO in server: SYN Shop Membership System Started...
[2023-10-25 17:55:02,533] INFO in server: -------------------------------------
 * Serving Flask app 'server'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (::)
 * Running on http://[::1]:8000
 * Running on http://[fd42:7c97:9426:8f29:211:3eff:fe43:a5ec]:8000
Press CTRL+C to quit
 * Restarting with stat
[2023-10-25 17:55:03,062] INFO in server: -------------------------------------
[2023-10-25 17:55:03,062] INFO in server: SYN Shop Membership System Started...
[2023-10-25 17:55:03,062] INFO in server: -------------------------------------
 * Debugger is active!
 * Debugger PIN: 111-454-085
```

## Setup for Production
The majority of the steps for a production set up are similar to the development environment, with the exception of using production values for the Auth0 Client Secret, the Stripe API Token, the Stripe Public Key and what the Pricing Map points to.

The one major change is that Production uses Gunicorn instead of the built-in Flask server.  It is also configured as a Systemd service in our environment.  An example service file is provided in the `service/` directory in the root folder.  Copy that over to `/etc/systemd/system` folder and just the values as necessary.  A quick and dirty recipe for this is:

```bash
$ cd membership.synshop.org/service
$ sudo cp membership.service /etc/systemd/system
$ sudo systemctl daemon-reload
$ sudo systemctl enable membership
```