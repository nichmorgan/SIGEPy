from random import randint
from typing import Union, Optional, overload

from correios.models.data import (
    SERVICE_PAC, SERVICE_PAC_INDUSTRIAL,
    SERVICE_SEDEX, SERVICE_SEDEX10, SERVICE_SEDEX12, SERVICE_E_SEDEX, SERVICE_SEDEX_INDUSTRIAL,
    REGIONAL_DIRECTIONS
)
from correios.client import Correios
from correios.models.user import *
from correios.models.posting import *
from correios.renderers.pdf import PostingReportPDFRenderer, PDF

class SIGEPy(Correios, PostingReportPDFRenderer):
    def __init__(self,
                 usr: str, pwd: str,
                 company_name: str, company_cnpj: str,
                 contract_regional_direction: Union[int, str], contract_number: str,
                 contract_post_card_number: str, contract_admin_code: str, **kwargs):
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
        # self._client = Correios(usr, pwd)

        self._contract = Contract(self._user, contract_number, contract_regional_direction)
        self._posting_card = PostingCard(self._contract, contract_post_card_number, contract_admin_code)

        self._packages = []

        self._posting_list = None

        render_kwargs = {k: kwargs.pop(k)
                         for k in filter(lambda k: k in ['page_size', 'shipping_labels_margin', 'posting_list_margin'],
                                         kwargs.copy())}
        self._render = PostingReportPDFRenderer(**render_kwargs)
        self._sender = None
        self._receiver = None

        Correios.__init__(self, usr, pwd, **kwargs)

    def get_user(self, *args, **kwargs) -> User:
        if not (args or kwargs):
            return self.user
        return super().get_user(*args, **kwargs)

    def get_posting_card_status(self, *args, **kwargs) -> Union[bool, None]:
        if not (args or kwargs):
            return super().get_posting_card_status(self.posting_card)
        return super().get_posting_card_status(*args, **kwargs)

    def request_tracking_codes(self, service: Union[Service, int, str], **kwargs) -> list:
        """
        Generates tracking codes.

        :param service: The service int / service object (i.e. PAC, SEDEX).
        :param quantity: The quantity of tracking codes to be generated.
        :return: List of tracking codes.
        """
        user = kwargs.get('user', self.user)
        return super().request_tracking_codes(user, Service.get(service), **kwargs)

    def close_posting_list(self, custom_id: Optional[int] = None, *args, **kwargs) -> PostingList:
        """
        Creates the pre-delivery's data.

        :param custom_id: A random integer as list id.
        :param drop_data_at_end: Erase sender, receiver and packages data after create the pre-delivery's data.
        :return: The pre-delivery's data as PostingList
        """

        if args or kwargs:
            return super().close_posting_list(*args, **kwargs)

        assert len(self._packages) > 0, 'No packages to send. Register at least one package to use this function.'
        assert isinstance(self.sender, Address), 'Invalid sender address.'
        assert isinstance(self.receiver, Address), 'Invalid receiver address.'

        if custom_id is None:
            custom_id = randint(1000, 9999999)

        closed_posting_list = PostingList(custom_id)
        for package in self.packages:
            label = ShippingLabel(
                posting_card=self.posting_card,
                sender=self.sender, receiver=self.receiver,
                service=package.service, tracking_code=self.request_tracking_codes(service=package.service)[0],
                package=package
            )

            closed_posting_list.add_shipping_label(label)

        closed_posting_list = super().close_posting_list(closed_posting_list, self.posting_card)
        self.posting_list = closed_posting_list
        self._render.set_posting_list(closed_posting_list)
        self._drop_posting_list_data()
        return closed_posting_list

    def verify_service_availability(self, *args, **kwargs) -> Union[bool, List[bool], None]:
        saida = []
        if args or kwargs:
            return super().verify_service_availability(*args, **kwargs)
        elif self.posting_list:
            label: ShippingLabel
            for label in self.posting_list.shipping_labels.values():
                saida.append(super().verify_service_availability(label.posting_card,
                                                          label.service,
                                                          label.sender.zip_code,
                                                          label.receiver.zip_code))

            return saida
        else:
            return None

    def _drop_posting_list_data(self) -> None:
        """
        Erase sender, receiver and packages data.

        :return: None
        """
        self._packages = []
        self._receiver = None
        self._sender = None

    def generate_delivery_labels_pdf(self, filepath: str, pdf: PDF = None) -> None:
        if self.posting_list:
            self._render.render_labels(pdf).save(filepath)
        else:
            raise Exception('The posting list is None.')

    def generate_delivery_posting_list_pdf(self, filepath: str, pdf: PDF = None) -> None:
        if self.posting_list:
            self._render.render_posting_list(pdf).save(filepath)
        else:
            raise Exception('The posting list is None.')

    def add_package(self, *args, **kwargs) -> None:
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
        if (not 'service' in kwargs) and (len(args) < 7):
            raise Exception('Service is required.')

        self._packages.append(Package(*args, **kwargs))

    def create_sender(self, *args, **kwargs) -> None:
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
        self._sender = Address(*args, **kwargs)

    def create_receiver(self, *args, **kwargs) -> None:
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
        self._receiver = Address(*args, **kwargs)

    # TODO More functions at SIGEP documentation

    @property
    def sender(self) -> Address:
        return self._sender

    @property
    def receiver(self) -> Address:
        return self._receiver

    @property
    def packages(self) -> List[Package]:
        return self._packages

    @property
    def user(self) -> User:
        return self._user

    @property
    def contract(self) -> Contract:
        return self._contract

    @property
    def posting_card(self) -> PostingCard:
        return self._posting_card

    @property
    def posting_list(self) -> PostingList:
        return self._posting_list

    @posting_list.setter
    def posting_list(self, posting_list: PostingList) -> None:
        self._posting_list = posting_list
        self._render.posting_list = posting_list

    @property
    def tracking_codes(self) -> List[TrackingCode]:
        if self.posting_list:
            label: ShippingLabel
            for label in self.posting_list.shipping_labels.values():
                yield label.tracking_code
        return None

    @property
    def delivery_time(self) -> List[int]:
        if self.posting_list:
            label: ShippingLabel
            for label in self.posting_list.shipping_labels.values():
                yield int(super().calculate_delivery_time(label.service,
                                                      label.sender.zip_code,
                                                      label.receiver.zip_code))
        return 0

    @property
    def freights(self) -> List[FreightResponse]:
        if isinstance(self.posting_list, PostingList):
            label: ShippingLabel
            for label in self.posting_list.shipping_labels.values():
                yield super().calculate_freights(
                    label.posting_card, [label.service],
                    label.sender.zip_code, label.receiver.zip_code,
                    label.package, label.value,
                    label.extra_services
                )[0]
        return None


if '__main__' == __name__:
    from data_samples.sample_data import *

    s = SIGEPy(*SIGEPY_DATA.values())
    s.create_sender(**SENDER_TEST)
    s.create_receiver(**RECEIVER_TEST)
    for pack_list in PACKS_SERVICE:
        s.add_package(**pack_list)
    s.close_posting_list()
    s.generate_delivery_labels_pdf('test_code.pdf')
    s.generate_delivery_posting_list_pdf('post.pdf')

    f = list(s.freights)

    print('posting_list')
