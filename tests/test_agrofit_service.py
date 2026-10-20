"""Tests for Agrofit catalog normalization without network calls."""

from app.services.agrofit_service import AgrofitService


def test_agrofit_normalizes_product_record():
    service = AgrofitService()
    record = service._normalize_record(
        {
            "Marca Comercial": "Produto X",
            "Ingrediente Ativo": "Glifosato",
            "Classe": "Herbicida",
            "Numero Registro": "12345",
            "Titular": "Empresa Y",
        }
    )

    assert record["product_name"] == "Produto X"
    assert record["active_ingredient"] == "Glifosato"
    assert record["category"] == "Herbicida"
    assert record["registration"] == "12345"


def test_agrofit_search_uses_local_cache():
    service = AgrofitService()
    service._products_cache = [
        service._normalize_record(
            {
                "Marca Comercial": "Produto X",
                "Ingrediente Ativo": "Glifosato",
                "Classe": "Herbicida",
            }
        )
    ]

    result = service.search_products(active_ingredient="glifosato")

    assert result["returned"] == 1
    assert result["products"][0]["product_name"] == "Produto X"
