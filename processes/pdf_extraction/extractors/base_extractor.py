from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseExtractor(ABC):
    """Base class for all text extractors."""
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract information from text.
        
        Args:
            text: The text to extract information from
            
        Returns:
            Dictionary containing extracted information
        """
        pass 