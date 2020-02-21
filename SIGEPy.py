from random import randint
from typing import Union, Optional

from correios.models.data import (
    SERVICE_PAC, SERVICE_PAC_INDUSTRIAL,
    SERVICE_SEDEX, SERVICE_SEDEX10, SERVICE_SEDEX12, SERVICE_E_SEDEX, SERVICE_SEDEX_INDUSTRIAL,
    REGIONAL_DIRECTIONS
)

from correios.client import Correios
from correios.models.user import User, Service
from correios.models.posting import PostingCard, PostingList, Contract, ShippingLabel, Address, Package
from correios.renderers import pdf


class SIGEPy:
    def __init__(self,
                 usr: str, pwd: str,
                 company_name: str, company_cnpj: str,
                 contract_regional_direction: Union[int, str], contract_number: str,
                 contract_post_card_number: str, contract_admin_code: str):
        """
        This class operate the web services of brazilian post service, Correios, named SIGEP.\n
        The basic usage is:
            1. Load the company credentials: sigep = SIGEP(**credentials);
            2. Register a sender: sigep.create_sender(**sender_data);
            3. Register a receiver: sigep.create_receiver(**receiver_data);
            4. Add delivery's packages: sigep.add_package(**package_data);
            5. Generate pre-delivery data: sigep.generate_pre_delivery_data();
            6. Generate posting list file: sigep.generate_delivery_posting_list_pdf(filepath);
            7. Generate delivery labels file: sigep.generate_delivery_labels_pdf(filepath).

        Its possible only generate tracking codes also:
            1. sigep.generate_tracking_codes(service_type, quantity_of_tracking_codes).

        :param usr: Company username.
        :param pwd: Company password.
        :param company_name: Company name.
        :param company_cnpj: Companny CNPJ.
        :param contract_regional_direction: Company Regional Direction.
        :param contract_number: Company number.
        :param contract_post_card_number: Company PostCard number.
        :param contract_admin_code: Company Administration code.
        """

        if isinstance(contract_regional_direction, str):
            contract_regional_direction = list(filter(lambda rd: rd[1]['code'] == contract_regional_direction,
                                                      REGIONAL_DIRECTIONS.items()))
            if len(contract_regional_direction) == 1:
                contract_regional_direction = contract_regional_direction[0]
            else:
                raise Exception('Invalid regional direction.')

        self._user = User(company_name, company_cnpj)
        self._client = Correios(usr, pwd)
        self._contract = Contract(self._user, contract_number, contract_regional_direction)
        self._posting_card = PostingCard(self._contract, contract_post_card_number, contract_admin_code)

        self._packages = []

        self._posting_list = None
        self._posting_list_renderer = pdf.PostingReportPDFRenderer()

        self._sender = None
        self._receiver = None

    def _drop_posting_list_data(self) -> None:
        """
        Erase sender, receiver and packages data.

        :return: None
        """
        self._packages = []
        self._receiver = None
        self._sender = None

    def generate_tracking_codes(self, service: Union[int, Service], quantity: int) -> list:
        """
        Generates tracking codes.

        :param service: The service int / service object (i.e. PAC, SEDEX).
        :param quantity: The quantity of tracking codes to be generated.
        :return: List of tracking codes.
        """
        if not isinstance(service, Service):
            service = Service.get(service)
        return self.client.request_tracking_codes(self.user, service, quantity)

    def generate_pre_delivery_data(self, custom_id: Optional[int] = None) -> PostingList:
        """
        Creates the pre-delivery's data.

        :param custom_id: A random integer as list id.
        :param drop_data_at_end: Erase sender, receiver and packages data after create the pre-delivery's data.
        :return: The pre-delivery's data as PostingList
        """
        assert len(self._packages) > 0, 'No packages to send. Register at least one package to use this function.'
        assert isinstance(self.sender, Address), 'Invalid sender address.'
        assert isinstance(self.receiver, Address), 'Invalid receiver address.'

        if custom_id is None:
            custom_id = randint(1, 9999999)

        closed_posting_list = PostingList(custom_id)
        for package in self.packages:
            label = ShippingLabel(
                posting_card=self.posting_card,
                sender=self.sender, receiver=self.receiver,
                service=package.service, tracking_code=self.generate_tracking_codes(package.service, 1)[0],
                package=package
            )

            closed_posting_list.add_shipping_label(label)

        closed_posting_list = self.client.close_posting_list(closed_posting_list, self.posting_card)
        self.posting_list = closed_posting_list

        self._drop_posting_list_data()
        return closed_posting_list

    def generate_delivery_labels_pdf(self, filepath: str) -> None:
        self._posting_list_renderer.render_labels().save(filepath)

    def generate_delivery_posting_list_pdf(self, filepath: str) -> None:
        self._posting_list_renderer.render_posting_list().save(filepath)

    def add_package(self, **package) -> None:
        """
        Add a Package class to delivery. Use the fields below (the service is required):\n
        package_type:
            int = TYPE_BOX,\n
            width: Union[float, int] = 0,\n
            height: Union[float, int] = 0,\n
            length: Union[float, int] = 0,\n
            diameter: Union[float, int] = 0,\n
            weight: Union[float, int] = 0,\n
            sequence: Tuple[int, int] = (1, 1),\n
            service: Union[Service, str, int, None] = None) -> None
        :param package: The fields of a Package class with service as required field
        :return: None
        """
        assert 'service' in package, "The package's service  is required."
        self._packages.append(Package(**package))

    def create_sender(self, **sender) -> None:
        """
        Register a sender to delivery. Parameters below:
            name: str,\n
            street: str,\n
            number: Union[int, str],\n
            city: str,\n
            state: Union[State, str],\n
            zip_code: Union[ZipCode, str],\n
            complement: str = "",\n
            neighborhood: str = "",\n
            phone: Union[Phone, str] = "",\n
            cellphone: Union[Phone, str] = "",\n
            email: str = "",\n
            latitude: Union[Decimal, Decimal, str] = "0.0",\n
            longitude: Union[Decimal, Decimal, str] = "0.0"\n
        :param sender: Address parameters.
        :return: None
        """
        self._sender = Address(**sender)

    def create_receiver(self, **receiver) -> None:
        """
        Register a receiver to delivery. Parameters below:
            name: str,\n
            street: str,\n
            number: Union[int, str],\n
            city: str,\n
            state: Union[State, str],\n
            zip_code: Union[ZipCode, str],\n
            complement: str = "",\n
            neighborhood: str = "",\n
            phone: Union[Phone, str] = "",\n
            cellphone: Union[Phone, str] = "",\n
            email: str = "",\n
            latitude: Union[Decimal, Decimal, str] = "0.0",\n
            longitude: Union[Decimal, Decimal, str] = "0.0"\n
        :param receiver: Address parameters.
        :return: None
        """
        self._receiver = Address(**receiver)

    # TODO More functions at SIGEP documentation

    @property
    def sender(self):
        return self._sender

    @property
    def receiver(self):
        return self._receiver

    @property
    def packages(self):
        return self._packages

    @property
    def user(self):
        return self._user

    @property
    def client(self):
        return self._client

    @property
    def contract(self):
        return self._contract

    @property
    def posting_card(self):
        return self._posting_card

    @property
    def posting_list(self):
        return self._posting_list

    @posting_list.setter
    def posting_list(self, posting_list: PostingList):
        self._posting_list = posting_list
        self._posting_list_renderer.posting_list = posting_list

    @property
    def tracking_codes(self):
        if self.posting_list:
            return map(lambda labels: labels.tracking_code.code,
                       self.posting_list.shipping_labels)
