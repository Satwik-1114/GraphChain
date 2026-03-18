// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FederatedIntegrity {

    struct LocalModel {
        address hospital;
        string modelHash;
        uint cycle;
    }

    struct GlobalModel {
        string modelHash;
        uint cycle;
        address owner;
    }

    LocalModel[] public localModels;
    GlobalModel[] public globalModels;

    event LocalHashStored(address hospital, string hash, uint cycle);
    event GlobalHashStored(string hash, uint cycle, address owner);

    function storeLocalHash(
        address hospital,
        string memory hash,
        uint cycle
    ) public {

        localModels.push(LocalModel(
            hospital,
            hash,
            cycle
        ));

        emit LocalHashStored(hospital, hash, cycle);
    }

    function storeGlobalHash(
        string memory hash,
        uint cycle
    ) public {

        globalModels.push(GlobalModel(
            hash,
            cycle,
            msg.sender
        ));

        emit GlobalHashStored(hash, cycle, msg.sender);
    }

    function getLocalModel(uint index)
        public view returns(address,string memory,uint)
    {
        LocalModel memory m = localModels[index];
        return (m.hospital, m.modelHash, m.cycle);
    }

    function getGlobalModel(uint index)
        public view returns(string memory,uint,address)
    {
        GlobalModel memory g = globalModels[index];
        return (g.modelHash, g.cycle, g.owner);
    }
}