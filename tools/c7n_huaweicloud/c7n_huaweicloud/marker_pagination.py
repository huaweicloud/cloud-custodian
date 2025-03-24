from abc import ABC, abstractmethod


# abstract method for pagination
class MarkerPagination(ABC):
    @abstractmethod
    def get_first_page_params(self):
        pass

    @abstractmethod
    def get_next_page_params(self, response):
        pass
