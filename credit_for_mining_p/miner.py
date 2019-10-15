import hashlib
import json
import requests
from uuid import uuid4
import time
import sys

def valid_proof(block_string, proof):
        """
        Validates the Proof:  Does hash(block_string, proof) contain 6
        leading zeroes?  Return true if the proof is valid
        :param block_string: <string> The stringified block to use to
        check in combination with `proof`
        :param proof: <int?> The value that when combined with the
        stringified previous block results in a hash that has the
        correct number of leading zeroes.
        :return: True if the resulting hash is a valid proof, False otherwise
        """
        hash = hashlib.sha256((f"{block_string}{proof}").encode()).hexdigest()
        return hash[:6] == "000000"

def get_proof(block):
    proof = 0
    block_string = json.dumps(block, sort_keys=True)
    while not valid_proof(block_string, proof):
        proof += 1
    return proof

if __name__ == '__main__':
    # What node are we interacting with?
    if len(sys.argv) > 1:
        node = sys.argv[1]
    else:
        node = "http://localhost:5000"
    # open file my_id using append, so if file doesn't exist, create it
    f = open("my_id", "a")
    f.close()
    # reopen the file to read id
    f = open("my_id")
    client_id = f.read()
    f.close()
    if not client_id:
        # create id and save it in file my_id
        client_id = str(uuid4()).replace('-', '')
        f = open("my_id", 'w')
        f.write(client_id)
        f.close()
    coins = 0
    # Run forever until interrupted
    while True:
        # Get the last block from the server and generate a new proof
        print("Starting the mining")
        start_time = time.time()
        response = requests.get(f'{node}/last_block')
        block = response.json()['last_block']
        new_proof = get_proof(block)
        print(f"proof: {new_proof}")

        # send proof to the server to build a new block
        data = {'proof': new_proof, 'id': client_id}
        res = requests.post(url=f'{node}/mine', json=data)
        # If block is created, add one coin
        if res.status_code == 200:
            end_time = time.time() 
            coins += 1
            print(f"{res.json()['message']}. Get one more coin! Total: {coins} - Done in {end_time-start_time} seconds.")
        else:
            print(res.text)
