"""Pydantic models for API request/response."""
from pydantic import BaseModel
from typing import Optional, List

# ── Vendors ──

class VendorCreate(BaseModel):
    name: str
    domain: str = ""
    icon: str = ""
    notes: str = ""

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    icon: Optional[str] = None
    notes: Optional[str] = None

# ── Vendor Keys ──

class VendorKeyCreate(BaseModel):
    vendor_id: int
    label: str = "default"
    api_key: str
    notes: str = ""

class VendorKeyUpdate(BaseModel):
    label: Optional[str] = None
    api_key: Optional[str] = None
    notes: Optional[str] = None

class VendorKeyOut(BaseModel):
    id: int
    vendor_id: int
    label: str
    api_key_masked: str
    balance: Optional[float] = None
    quota: Optional[float] = None
    status: str = "active"
    notes: str = ""

class VendorKeyNested(BaseModel):
    id: int
    label: str
    api_key_masked: str
    balance: Optional[float] = None
    quota: Optional[float] = None
    status: str = "active"
    notes: str = ""

class ProviderNested(BaseModel):
    id: int
    name: str
    base_url: str
    vendor_key_id: Optional[int] = None
    vendor_key_label: str = ""
    notes: str

class VendorOut(BaseModel):
    id: int
    name: str
    domain: str
    icon: str = ""
    notes: str
    keys: List[VendorKeyNested] = []
    providers: List[ProviderNested] = []

# ── Providers ──

class ProviderCreate(BaseModel):
    vendor_id: int
    vendor_key_id: Optional[int] = None
    name: str
    base_url: str
    notes: str = ""

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    vendor_key_id: Optional[int] = None
    base_url: Optional[str] = None
    notes: Optional[str] = None

class ProviderOut(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str = ""
    vendor_key_id: Optional[int] = None
    vendor_key_label: str = ""
    name: str
    base_url: str
    api_key_masked: str
    notes: str

# ── Bindings ──

class BindingCreate(BaseModel):
    provider_id: int
    adapter_id: str
    target_provider_name: str = ""
    auto_sync: bool = True

class BindingOut(BaseModel):
    id: int
    provider_id: int
    provider_name: str = ""
    adapter_id: str
    adapter_label: str = ""
    target_provider_name: str
    auto_sync: bool

# ── Adapters ──

class AdapterRegister(BaseModel):
    id: str
    label: str
    config_path: str = ""
