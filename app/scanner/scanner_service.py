"""
Scanner Service - Interface for physical document scanners
Windows: Uses WIA (Windows Image Acquisition) via COM
Linux: Uses SANE (not yet implemented)
"""

import logging
import os
import tempfile
from typing import Optional, List, Dict, Any
from PIL import Image
import platform

logger = logging.getLogger("scanner_service")


class WIAScanner:
    """Windows Image Acquisition scanner interface"""
    
    def __init__(self):
        self.wia = None
        self._init_wia()
    
    def _init_wia(self):
        """Initialize WIA COM interface"""
        try:
            import win32com.client
            self.wia = win32com.client.Dispatch("WIA.CommonDialog")
            logger.info("✓ WIA scanner interface initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WIA: {e}")
            self.wia = None
    
    def list_devices(self) -> List[Dict[str, str]]:
        """List available WIA devices"""
        if not self.wia:
            return []
        
        try:
            import win32com.client
            device_manager = win32com.client.Dispatch("WIA.DeviceManager")
            
            devices = []
            for i in range(1, device_manager.DeviceInfos.Count + 1):
                device_info = device_manager.DeviceInfos.Item(i)
                devices.append({
                    'name': str(device_info.Properties("Name").Value),
                    'id': str(device_info.DeviceID),
                    'vendor': str(device_info.Properties("Manufacturer").Value) if hasattr(device_info.Properties("Manufacturer"), "Value") else "Unknown",
                    'model': str(device_info.Properties("Name").Value),
                    'type': 'Scanner'
                })
                logger.info(f"Found WIA device: {devices[-1]['name']}")
            
            return devices
        except Exception as e:
            logger.error(f"Error listing WIA devices: {e}")
            return []
    
    def scan(self, device_id: Optional[str] = None) -> Optional[Image.Image]:
        """Scan a document using WIA"""
        if not self.wia:
            raise Exception("WIA not initialized")
        
        try:
            import win32com.client
            
            # Get device - either by ID or show selection dialog
            if device_id:
                # Connect to specific device by ID
                logger.info(f"Connecting to scanner: {device_id}")
                device_manager = win32com.client.Dispatch("WIA.DeviceManager")
                device = None
                for i in range(1, device_manager.DeviceInfos.Count + 1):
                    dev_info = device_manager.DeviceInfos.Item(i)
                    if str(dev_info.DeviceID) == device_id:
                        device = dev_info.Connect()
                        break
                
                if not device:
                    logger.error(f"Scanner not found: {device_id}")
                    raise Exception(f"Scanner not found: {device_id}")
            else:
                # Show scanner selection dialog
                logger.info("Showing scanner selection dialog...")
                device = self.wia.ShowSelectDevice()
                if not device:
                    logger.warning("No device selected")
                    return None
            
            # Scan image
            logger.info("Starting scan...")
            item = device.Items(1)
            image_file = self.wia.ShowTransfer(item, "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}", False)
            
            if not image_file:
                logger.warning("Scan cancelled")
                return None
            
            # Save to temporary file
            temp_path = tempfile.mktemp(suffix=".bmp")
            image_file.SaveFile(temp_path)
            
            # Load with PIL
            pil_image = Image.open(temp_path)
            result = pil_image.copy()
            pil_image.close()
            
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass
            
            logger.info("✓ Scan completed")
            return result
            
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            raise


class ScannerService:
    """
    Cross-platform scanner service
    Windows: Uses WIA via COM
    Linux: Not yet implemented
    """
    
    def __init__(self):
        self.backend = None
        self.wia_scanner = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize scanner backend based on OS"""
        os_name = platform.system()
        logger.info(f"Detected OS: {os_name}")
        
        if os_name == "Windows":
            try:
                self.wia_scanner = WIAScanner()
                if self.wia_scanner.wia:
                    self.backend = 'wia'
                    logger.info("✓ Initialized WIA scanner backend (Windows)")
                else:
                    self.backend = None
                    logger.warning("WIA not available - scanner features disabled")
            except Exception as e:
                logger.error(f"Failed to initialize WIA: {e}")
                self.backend = None
        else:
            logger.warning(f"Scanner support not implemented for {os_name}")
            self.backend = None
    
    def list_scanners(self) -> List[Dict[str, str]]:
        """
        List all available scanners
        
        Returns:
            List of scanner info dicts with 'name' and 'vendor' keys
        """
        if self.backend is None or not self.wia_scanner:
            logger.warning("Scanner backend not initialized")
            return []
        
        try:
            logger.info(f"Listing scanners using {self.backend} backend...")
            devices = self.wia_scanner.list_devices()
            logger.info(f"Found {len(devices)} device(s)")
            
            if not devices:
                logger.warning("No scanners found. Check scanner connection and drivers.")
            
            return devices
            
        except Exception as e:
            logger.error(f"Error listing scanners: {e}")
            return []
    
    def scan_document(
        self,
        scanner_name: Optional[str] = None,
        color_mode: str = 'color',
        dpi: int = 300,
        scan_mode: str = 'flatbed'
    ) -> List[Image.Image]:
        """
        Scan document from physical scanner
        
        Args:
            scanner_name: Scanner device name (None = show selection dialog)
            color_mode: 'color', 'gray', or 'lineart' (not implemented yet)
            dpi: Scanning resolution (not configurable via WIA CommonDialog)
            scan_mode: 'flatbed' or 'adf' (not configurable via WIA CommonDialog)
        
        Returns:
            List of PIL Image objects (one per page)
        """
        if self.backend is None or not self.wia_scanner:
            raise Exception("Scanner backend not initialized")
        
        try:
            logger.info(f"Starting scan (scanner={scanner_name or 'dialog'}, mode={color_mode}, dpi={dpi})...")
            
            # Find device ID from scanner name
            device_id = None
            if scanner_name:
                devices = self.wia_scanner.list_devices()
                for device in devices:
                    if device['name'] == scanner_name:
                        device_id = device['id']
                        break
                
                if not device_id:
                    logger.warning(f"Scanner '{scanner_name}' not found, showing selection dialog")
            
            # Use WIA to scan
            scanned_image = self.wia_scanner.scan(device_id)
            
            if not scanned_image:
                raise Exception("Scan cancelled or failed")
            
            logger.info("✓ Successfully scanned 1 page")
            return [scanned_image]
            
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            raise
    
    def cleanup(self):
        """Cleanup scanner resources"""
        logger.info("Scanner cleanup (no resources to release)")


# Singleton instance
_scanner_service = None

def get_scanner_service() -> ScannerService:
    """Get or create scanner service singleton"""
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = ScannerService()
    return _scanner_service
