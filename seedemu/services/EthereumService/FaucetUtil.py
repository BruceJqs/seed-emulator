from typing import Dict
from seedemu.core import AddressFamily, Configurable, formatHost, getNodeAddress, normalizeAddressFamily
from seedemu.core.Emulator import Emulator

from .EthTemplates import (
    format_fund_accounts_script,
    format_faucet_fund_url,
    format_faucet_url,
    format_fund_curl,
)

class FaucetUtil(Configurable):
    __vnode_name:str
    __port:int
    __fund_list:list
    __faucet_server_address:str
    __is_configured:bool
    __endpoint_address_family: AddressFamily

    def __init__(self, endpointAddressFamily=AddressFamily.IPv4):
        super().__init__()
        self.__is_configured = False
        self.__fund_list = []
        self.__vnode_name = ""
        self.__port = -1
        self.__faucet_server_address = ""
        self.__endpoint_address_family = normalizeAddressFamily(endpointAddressFamily)

    def setEndpointAddressFamily(self, family):
        self.__endpoint_address_family = normalizeAddressFamily(family)
        return self

    def configure(self, emulator: Emulator):
        super().configure(emulator)
        self.__faucet_server_address = self.__getIpByVnodeName(
                     nodename=self.__vnode_name, emulator=emulator)
        assert self.__faucet_server_address != '', 'Failed to get ip address of the faucet server by its vnode name. please check the vnode name is valid'
        self.__is_configured = True

    def setFaucetServerInfo(self, vnode, port):
        self.__vnode_name = vnode
        self.__port = port
        return self


    def addFund(self, recipientAddress:str, amount:int):
        self.__fund_list.append((recipientAddress, amount))
        return self

    
    def getFaucetFundUrl(self):
        return format_faucet_fund_url(self.__faucet_server_address, self.__port)
    

    def getFacuetUrl(self):
        return format_faucet_url(self.__faucet_server_address, self.__port)
     
    
    def getFundApi(self, recipientAddress:str, amount:int):
        return format_fund_curl(
                     recipientAddress,
                     amount,
                     self.__faucet_server_address,
                     self.__port)


    def getFundScript(self):
        assert self.__is_configured, 'configure method should be called ahead.'
        
        funds_list = []
        for recipient, amount in self.__fund_list:
            funds_list.append(self.getFundApi(recipient, amount))
            
        return format_fund_accounts_script(
            formatHost(self.__faucet_server_address),
            self.__port,
            999999,
            ';'.join(funds_list),
        )

    
    def __getIpByVnodeName(self, nodename:str, emulator:Emulator) -> str:
        node = emulator.getBindingFor(nodename)
        address = getNodeAddress(node, self.__endpoint_address_family, preferLocal=True)
        assert address is not None, 'Node {} has no {} address.'.format(
            node.getName(),
            self.__endpoint_address_family.value,
        )
        return str(address)
