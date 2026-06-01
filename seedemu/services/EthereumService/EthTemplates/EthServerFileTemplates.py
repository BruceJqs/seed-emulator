from typing import Dict
import os

from seedemu.core import formatUrl

def get_file_content(filename):
    """!
    @brief Get the content of a file
    @param filename the file name (relative path)
    @return the content of the file
    """
    real_filename = os.path.dirname(os.path.realpath(__file__)) + "/" + filename
    with open(real_filename, "r") as file:
        return file.read()


EthServerFileTemplates: Dict[str, str] = {
        'bootstrapper':        get_file_content("files_ethereum/bootstrapper.sh"),
        'beacon_bootstrapper': get_file_content("files_ethereum/beacon_bootstrapper.sh"),
        'fetch_bn_enr':    get_file_content("files_ethereum/fetch_bn_enr.sh"),
        'vc_bootstrapper': get_file_content("files_ethereum/vc_bootstrapper.sh"),
}

UtilityServerFileTemplates: Dict[str, str] = {
        'fund_account':    get_file_content("files_utility/fund_account.py"),
        'deploy_contract': get_file_content("files_utility/deploy_contract.py"),
        'utility_server':  get_file_content("files_utility/utility_server.py"),
        'server_setup':    get_file_content("files_utility/utility_server_setup.sh")
}

FaucetServerFileTemplates: Dict[str, str] = {
        'faucet_server':   get_file_content("files_faucet/faucet_server.py"),
        'fund_accounts':   get_file_content("files_faucet/fund_accounts.sh"),
        'fundme':          get_file_content("files_faucet/fundme.py"),
        'faucet_url':      "http://{address}:{port}/",
        'faucet_fund_url': "http://{address}:{port}/fundme",
        'fund_curl': "curl -X POST -d 'address={recipient}&amount={amount}' http://{address}:{port}/fundme"
}


def format_faucet_url(address, port):
    return formatUrl("http", address, port, "/")


def format_faucet_fund_url(address, port):
    return formatUrl("http", address, port, "/fundme")


def format_fund_curl(recipient, amount, address, port):
    return "curl -X POST -d 'address={}&amount={}' {}".format(
        recipient,
        amount,
        format_faucet_fund_url(address, port),
    )


def format_fund_accounts_script(address, port, max_attempts, fund_command):
    template = FaucetServerFileTemplates["fund_accounts"].replace(
        'SERVER_URL="http://{address}:{port}"',
        'SERVER_URL="{server_url}"',
    )
    return template.format(
        address=address,
        port=port,
        server_url=formatUrl("http", address, port),
        max_attempts=max_attempts,
        fund_command=fund_command,
    )
