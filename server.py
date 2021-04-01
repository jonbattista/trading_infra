from flask import Flask
import requests

app = Flask(__name__)

@app.route('/', methods=["POST"])

def alpaca():
    key_id = request.args.get('key_id')

    secret_key = request.args.get('secret_key')

    if key_id is not None and secret_key is not None:
        headers = Headers()

        url = 'https://api.alpaca.markets/v2/orders'

        headers.add('APCA_API_SECRET_KEY', key_id)
        headers.add('APCA_API_SECRET_KEY', secret_key)

        response = requests.post(url, data=data, headers=headers)

        print(response)
    
if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)