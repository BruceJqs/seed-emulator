#!/usr/bin/env python3
# encoding: utf-8

import unittest as ut
from .SEEDBlockchain import Wallet
from web3 import Web3
from seedemu import *
import time
from tests import SeedEmuTestCase
import requests


class EthereumPOWTestCase(SeedEmuTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.wallet1 = Wallet(chain_id=1337)
        for name in ['Alice', 'Bob', 'Charlie', 'David', 'Eve']:
            cls.wallet1.createAccount(name)

        return

    def test_pow_chain_connection(self):
        url = 'http://10.152.0.71:8540'

        i = 1
        current_time = time.time()
        while True:
            self.printLog("\n----------Trial {}----------".format(i))
            if time.time() - current_time > 600:
                self.printLog("TimeExhausted: 600 sec")
                break
            try:
                self.wallet1.connectToBlockchain(url)
                self.printLog("Connection Succeed: ", url)
                break
            except Exception as e:
                self.printLog(e)
                time.sleep(20)
                i += 1
        self.assertTrue(self.wallet1._web3.isConnected())
    
    def test_pow_chain_id(self):
        self.assertEqual(self.wallet1._web3.eth.chain_id, 1337)
    
    def test_pow_send_transaction(self):
        remain_time = 1200
        self.printLog("\n----------------------------------------")
        self.printLog("Waiting for pow to mine new block (max waiting time : 1200 sec)".format(remain_time))
        while True:
            blockNumber = self.wallet1._web3.eth.getBlock('latest').number
            self.printLog("\n----------------------------------------")
            self.printLog("Current Block Number : {}".format(blockNumber))
            self.printLog("Remaining Time : {} sec".format(remain_time))
            time.sleep(10)
            remain_time -= 10
            if blockNumber > 0: break
            if remain_time <= 0: break
        
        recipient = self.wallet1.getAccountAddressByName('Bob')
        txhash = self.wallet1.sendTransaction(recipient, 0.1, sender_name='Alice', wait=True, verbose=False)
        self.assertTrue(self.wallet1.getTransactionReceipt(txhash)["status"], 1)
    
    def test_pow_chain_consensus(self):
        config = dict(self.wallet1._web3.geth.admin.nodeInfo().protocols.eth.config)
        self.assertTrue("ethash" in config.keys())

    def test_pow_peer_counts(self):
        peer_counts = len(self.wallet1._web3.geth.admin.peers())
        self.assertEqual(peer_counts, 4)

    def test_import_account(self):
        self.assertEqual(self.wallet1._web3.eth.getBalance(Web3.toChecksumAddress("9f189536def35811e1a759860672fe49a4f89e94")), 10)
    
    def test_pow_emulator_account(self):
        accounts = []
        for i in range(1,5):
            accounts.extend(EthAccount.createEmulatorAccountsFromMnemonic(i, mnemonic="great awesome fun seed security lab protect system network prevent attack future", balance=32*EthUnit.ETHER.value, total=1, password="admin"))
        for account in accounts:
            self.assertTrue(self.wallet1._web3.eth.getBalance(account.address) >= 32*EthUnit.ETHER.value)

    def test_pow_create_account(self):
        account = EthAccount.createEmulatorAccountFromMnemonic(3, mnemonic="great awesome fun seed security lab protect system network prevent attack future", balance=20*EthUnit.ETHER.value, index=1, password="admin")
        self.assertTrue(self.wallet1._web3.eth.getBalance(account.address) >= 20*EthUnit.ETHER.value)

    def test_static_fund(self):
        fund_address = "0x40e38EF94ab2bC9506167D478821ffd55ff2d88d"
        # Set maximum number of attempts
        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            if self.wallet1._web3.eth.getBalance(fund_address) >= 2*EthUnit.ETHER.value:
                break
            else:
                # Increment the attempts counter
                attempts += 1
                # Wait for a short duration before trying again (e.g., 5 seconds)
                time.sleep(10)
        self.assertTrue(self.wallet1._web3.eth.getBalance(fund_address) >= 2*EthUnit.ETHER.value)

    def test_dynamic_fund(self):
        max_attempts = 20
        attempts = 0

        while attempts < max_attempts:
            try:
                # Send the POST request
                response = requests.get('http://10.160.0.71:80/')
                # Check if the request was successful (status code 200)
                if response.status_code == 200:
                    print("POST request successful")
                    break  # Exit the loop if successful
                else:
                    print(f"POST request failed with status code {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}")
            
            # Increment the attempts counter
            attempts += 1
            # Wait for a short duration before trying again (e.g., 5 seconds)
            time.sleep(10)
        fund_address = "0x9e4f73dE97FEB05FE4e3c0d42B92585C9A0c0E91"

        # Define the URL of faucet API endpoint
        url = 'http://10.160.0.71:80/fundme'
        # Define the parameters to send in the POST request
        params = {'address': fund_address, 'amount': 5}
        # Send the POST request
        response = requests.post(url, data=params)
        print(response)
        while attempts < max_attempts:
            if self.wallet1._web3.eth.getBalance(fund_address) >= 5*EthUnit.ETHER.value:
                break
            else:
                # Increment the attempts counter
                attempts += 1
                # Wait for a short duration before trying again (e.g., 5 seconds)
                time.sleep(10)

        self.assertTrue(self.wallet1._web3.eth.getBalance(fund_address) >= 5*EthUnit.ETHER.value)

    @classmethod
    def get_test_suite(cls):
        test_suite = ut.TestSuite()
        test_suite.addTest(cls('test_pow_chain_connection'))
        test_suite.addTest(cls('test_pow_chain_id'))
        test_suite.addTest(cls('test_pow_chain_consensus'))
        test_suite.addTest(cls('test_import_account'))
        test_suite.addTest(cls('test_pow_emulator_account'))
        test_suite.addTest(cls('test_pow_create_account'))
        test_suite.addTest(cls('test_pow_send_transaction'))
        test_suite.addTest(cls('test_pow_peer_counts'))
        return test_suite

if __name__ == "__main__":
    test_suite = EthereumPOWTestCase.get_test_suite()

    res = ut.TextTestRunner(verbosity=2).run(test_suite)

    EthereumPOWTestCase.printLog("----------Test #%d--------=")
    num, errs, fails = res.testsRun, len(res.errors), len(res.failures)
    EthereumPOWTestCase.printLog("score: %d of %d (%d errors, %d failures)" % (num - (errs+fails), num, errs, fails))
    
