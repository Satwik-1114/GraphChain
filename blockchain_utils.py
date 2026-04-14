import json
from web3 import Web3
from config import INFURA_URL, CONTRACT_ADDRESS as _CONTRACT_ADDRESS
# ==========================================================
# BLOCKCHAIN SETUP
# ==========================================================

w3 = Web3(Web3.HTTPProvider(INFURA_URL))

with open("blockchain/FederatedIntegrity.json") as f:
    artifact = json.load(f)

contract_abi = artifact["abi"]

contract_address = Web3.to_checksum_address(_CONTRACT_ADDRESS)

contract = w3.eth.contract(
    address=contract_address,
    abi=contract_abi
)

# ==========================================================
# BLOCKCHAIN VERIFICATION
# ==========================================================

def get_blockchain_global_hash():
    try:
        events = contract.events.GlobalHashStored.get_logs(
            from_block=0,
            to_block="latest"
        )

        if not events:
            return None

        latest = events[-1]
        blockchain_hash = latest["args"]["hash"]
        return blockchain_hash

    except Exception as e:
        print("Blockchain error:", e)
        return None
