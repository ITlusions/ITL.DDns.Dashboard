import os
import dns.query
import dns.zone
import dns.tsigkeyring
import dns.message
from flask import Flask, render_template
from flask_socketio import SocketIO
from pydantic_settings import BaseSettings
import time
from datetime import datetime
import logging
import socket

# Pydantic Settings to load environment variables
class Settings(BaseSettings):
    domain: str = 'public.k8s.int.itlusions.com'
    ns_server: str = '192.168.1.241'
    ns_server_port: int = 5354
    key_name: str = 'externaldns'
    key_secret: str = os.getenv("DNS_KEY_SECRET", "eJalv42CfCjaGVOwGukGD5E6gAtNw+tZRFPOqkhFYZU=")  # Load from .env for security

    class Config:
        env_prefix = 'DNS_'  # Environment variable prefix
        env_file = '.env'    # Specify the .env file

# Load settings
settings = Settings()

# Flask app and SocketIO initialization
app = Flask(__name__)
socketio = SocketIO(app)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Global variable to store the last known SOA serial
last_serial = None
last_poll = None

# Global variable to store DNS records in memory
dns_records = []

def get_soa_serial():
    """Fetch the current SOA serial number of the DNS zone."""
    try:
        logging.debug(f"Fetching SOA record for {settings.domain} from {settings.ns_server}.")
        
        # Create an SOA query
        query = dns.message.make_query(settings.domain, dns.rdatatype.SOA)
        response = dns.query.udp(query, settings.ns_server, port=settings.ns_server_port)

        # Extract the SOA record from the response
        for answer in response.answer:
            if answer.rdtype == dns.rdatatype.SOA:
                soa_record = answer[0]
                logging.info(f"Fetched SOA serial: {soa_record.serial}")
                return soa_record.serial
    except Exception as e:
        logging.error(f"Error fetching SOA record: {e}")
        return None

def get_dns_records():
    """Fetch DNS records using zone transfer if SOA serial has changed."""
    global last_serial
    global last_poll
    global dns_records  # Access the global variable

    # Check current SOA serial
    current_serial = get_soa_serial()
    if current_serial is None:
        logging.warning("Failed to retrieve current SOA serial. Skipping record fetch.")
        return {'error': 'Could not retrieve SOA serial'}

    # Skip fetching if the SOA serial hasn't changed
    if current_serial == last_serial:
        logging.info("SOA serial has not changed. No need to fetch records.")
        return {'version': current_serial, 'records': dns_records}  # Return cached records

    last_serial = current_serial  # Update last known serial

    # Proceed with zone transfer
    logging.info("SOA serial has changed, proceeding with zone transfer.")
    keyring = dns.tsigkeyring.from_text({settings.key_name: settings.key_secret})

    try:
        zone = dns.zone.from_xfr(
            dns.query.xfr(where=settings.ns_server, zone=settings.domain, port=settings.ns_server_port, keyring=keyring, keyalgorithm='hmac-sha256')
        )
        last_poll = time.time()
        logging.info("Zone transfer successful.")
    except dns.exception.DNSException as e:
        logging.error(f"DNS error during zone transfer: {e}")
        return {'error': str(e)}
    except Exception as e:
        logging.error(f"General error during zone transfer: {e}")
        return {'error': str(e)}

    # Collect records from the transferred zone
    records = []
    for name, node in zone.nodes.items():
        for _record in node.rdatasets:
            for rdata in _record:
                record = {
                    'name': name.to_text(),
                    'type': dns.rdatatype.to_text(_record.rdtype),
                    'data': rdata.to_text(),
                    'rdataset': _record.to_text(),
                    'ttl': _record.ttl
                }
                records.append(record)
                logging.debug(f"Found record: {record}")

    # Store the records in memory for subsequent access
    dns_records = records

    logging.info(f"Total records found: {len(records)}")
    return {'version': current_serial, 'records': records}

def fetch_and_emit_records():
    """Poll DNS records every 30 seconds."""
    while True:
        records = get_dns_records()
        if records.get('records'):
            socketio.emit('dns_records', {'records': records['records']})
            logging.info("Emitted DNS records to clients.")
        else:
            logging.info("No new DNS records to emit.")
        time.sleep(600)  # Poll every 30 seconds

@app.route('/')
def index():
    """Serve the DNS records when the page loads."""
    logging.info(f"Last Poll Time: {datetime.fromtimestamp(last_poll)}.")
    logging.info("Index route accessed.")
    # Serve the in-memory records on page load
    return render_template('index.html', records=dns_records)

@socketio.on('connect')
def handle_connect():
    logging.info("Client connected. Emitting DNS records.")
    socketio.emit('dns_records', {'records': dns_records})

if __name__ == "__main__":
    logging.info("Starting the application...")
    socketio.start_background_task(target=fetch_and_emit_records)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
