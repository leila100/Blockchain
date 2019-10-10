import hashlib
import json
from time import time
from uuid import uuid4
import sys
from flask import Flask, jsonify, request
import requests


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        self.genesis_block()

    def genesis_block(self):
        block = {
            'index': 1,
            'timestamp': 0,
            'transactions': [],
            'proof': 1,
            'previous_hash': 1,
        }
        self.chain.append(block)

    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain

        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous Block
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined Block

        :param sender: <str> Address of the Recipient
        :param recipient: <str> Address of the Recipient
        :param amount: <int> Amount
        :return: <int> The index of the BLock that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block

        :param block": <dict> Block
        "return": <str>
        """
        # json.dumps converts json into a string
        # hashlib.sha246 is used to createa hash
        # It requires a `bytes-like` object, which is what
        # .encode() does.  It convertes the string to bytes.
        # We must make sure that the Dictionary is Ordered,
        # or we'll have inconsistent hashes

        block_string = json.dumps(block, sort_keys=True).encode()

        # By itself, this function returns the hash in a raw string
        # that will likely include escaped characters.
        # This can be hard to read, but .hexdigest() converts the
        # hash to a string using hexadecimal characters, which is
        # easer to work with and understand.  
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
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

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid.  We'll need this
        later when we are a part of a network.

        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """

        prev_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{prev_block}')
            print(f'{block}')
            print("\n-------------------\n")
            # Check that the hash of the block is correct
            prev_hash = self.hash(prev_block)
            if prev_hash != block['previous_hash']:
                return False

            # Check that the Proof of Work is correct
            block_string = json.dumps(prev_block, sort_keys=True)
            if not self.valid_proof(block_string, block['proof']):
                return False

            prev_block = block
            current_index += 1

        return True

    def register_node(self, node):
        self.nodes.add(node)

    def allert_nodes(self, block):
        for node in self.nodes:
            response = requests.post(node + '/block/new', json={'block': block})
            message = response.json()['message']
            print(f'Block broadcasted to {node}: {message}')

    def get_updated_chain(self):
        longest_chain = self.chain
        for node in self.nodes:
            response = requests.get(node + '/chain')
            node_chain = response.json()['chain']
            if self.valid_chain(node_chain):
                if len(node_chain) > longest_chain:
                    longest_chain = node_chain
        if longest_chain is not self.chain:
            self.chain = longest_chain
            print(f"Chain has been changed to {longest_chain}")


# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
# node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['POST'])
def mine():
    values = request.get_json()
    required = ['proof', 'id']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # check validity of proof
    last_block = blockchain.last_block
    block_string = json.dumps(last_block, sort_keys=True)
    if not blockchain.valid_proof(block_string, values['proof']):
        return 'Proof not valid', 400

    # We must receive a reward for finding the proof.
    blockchain.new_transaction(
        sender="0",
        recipient=values['id'],
        amount=1
    )
    # The sender is "0" to signify that this node has mine a new coin
    # The recipient is the current node, it did the mining!
    # The amount is 1 coin as a reward for mining the next block

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(values['proof'], previous_hash)

    # Let all the other nodes know that a new block has been created
    blockchain.allert_nodes(block)

    # Send a response with the new block
    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing Values', 400

    # Create a new Transaction
    index = blockchain.new_transaction(values['sender'],
                                       values['recipient'],
                                       values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/validate_chain', methods=['GET'])
def validate_chain():
    valid = blockchain.valid_chain(blockchain.chain)
    response = {
        "valid": valid
    }
    return jsonify(response), 200


@app.route('/last_block', methods=['GET'])
def last():
    last_block = blockchain.last_block
    response = {
        'last_block': last_block
    }
    return jsonify(response), 200


#############Additional Code Added by our Colleagues################

@app.route('/block/new', methods=['POST'])
def new_block():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['block']
    if not all(k in values for k in required):
        return 'Missing Values', 400

    new_block = values['block']
    last_block = blockchain.last_block
    # Check that the new block index is 1 higher than our last block
    if new_block['index'] == last_block['index'] + 1:
        # check that the new block 'previous_hash' is same as last_block hashed
        if blockchain.hash(last_block) == new_block['previous_hash']:
            # check that it has a valid proof
            block_string = json.dumps(last_block, sort_keys=True)
            if blockchain.valid_proof(block_string, new_block['proof']):
                # new block is valid, add it to the chain
                blockchain.chain.append(new_block)
                response = {
                    'message': "New block added to chain"
                }
            else:
                response = {
                    'message': "New block has invalid proof"
                }
        else:
            response = {
                'message': "New block has invalid previous hash"
            }
    else:
        blockchain.get_updated_chain()
        response = {
            'message': "New block has an invalid index. Updated chain."
        }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

if __name__ == '__main__':
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 5000
    app.run(host='0.0.0.0', port=port)