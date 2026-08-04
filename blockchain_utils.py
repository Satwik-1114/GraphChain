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
        latest_block = w3.eth.block_number
        chunk_size = 9000  # Safe limit below the 10,000 restriction
        current_to_block = latest_block
        
        # We search backwards in chunks to find the most recent event.
        # We limit the search to the last ~50,000 blocks to avoid an infinite loop 
        # on empty contracts, which is more than enough for recent testnet transactions.
        while current_to_block >= 0 and (latest_block - current_to_block) < 50000:
            current_from_block = max(0, current_to_block - chunk_size)
            
            events = contract.events.GlobalHashStored.get_logs(
                from_block=current_from_block,
                to_block=current_to_block
            )
            
            if events:
                # Found events, return the hash from the most recent one
                latest = events[-1]
                return latest["args"]["hash"]
            
            if current_from_block == 0:
                break
                
            current_to_block = current_from_block - 1

        return None

    except Exception as e:
        print("Blockchain error:", e)
        return None
