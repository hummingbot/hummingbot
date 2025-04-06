from .rest_base import RESTBase


class RESTClient(RESTBase):
    """
    **RESTClient**
    _____________________________

    Initialize using RESTClient

    __________

    **Parameters**:

    - **api_key | Optional (str)** - The API key
    - **api_secret | Optional (str)** - The API key secret
    - **key_file | Optional (IO | str)** - Path to API key file or file-like object
    - **base_url | (str)** - The base URL for REST requests. Default set to "https://api.coinbase.com"
    - **timeout | Optional (int)** - Set timeout in seconds for REST requests
    - **verbose | Optional (bool)** - Enables debug logging. Default set to False
    - **rate_limit_headers | Optional (bool)** - Enables rate limit headers. Default set to False

    """

    from .accounts import get_account, get_accounts
    from .convert import commit_convert_trade, create_convert_quote, get_convert_trade
    from .data_api import get_api_key_permissions
    from .fees import get_transaction_summary
    from .futures import (
        cancel_pending_futures_sweep,
        get_current_margin_window,
        get_futures_balance_summary,
        get_futures_position,
        get_intraday_margin_setting,
        list_futures_positions,
        list_futures_sweeps,
        schedule_futures_sweep,
        set_intraday_margin_setting,
    )
    from .market_data import get_candles, get_market_trades
    from .orders import (
        cancel_orders,
        close_position,
        create_order,
        edit_order,
        get_fills,
        get_order,
        limit_order_fok,
        limit_order_fok_buy,
        limit_order_fok_sell,
        limit_order_gtc,
        limit_order_gtc_buy,
        limit_order_gtc_sell,
        limit_order_gtd,
        limit_order_gtd_buy,
        limit_order_gtd_sell,
        limit_order_ioc,
        limit_order_ioc_buy,
        limit_order_ioc_sell,
        list_orders,
        market_order,
        market_order_buy,
        market_order_sell,
        preview_edit_order,
        preview_limit_order_fok,
        preview_limit_order_fok_buy,
        preview_limit_order_fok_sell,
        preview_limit_order_gtc,
        preview_limit_order_gtc_buy,
        preview_limit_order_gtc_sell,
        preview_limit_order_gtd,
        preview_limit_order_gtd_buy,
        preview_limit_order_gtd_sell,
        preview_limit_order_ioc,
        preview_limit_order_ioc_buy,
        preview_limit_order_ioc_sell,
        preview_market_order,
        preview_market_order_buy,
        preview_market_order_sell,
        preview_order,
        preview_stop_limit_order_gtc,
        preview_stop_limit_order_gtc_buy,
        preview_stop_limit_order_gtc_sell,
        preview_stop_limit_order_gtd,
        preview_stop_limit_order_gtd_buy,
        preview_stop_limit_order_gtd_sell,
        preview_trigger_bracket_order_gtc,
        preview_trigger_bracket_order_gtc_buy,
        preview_trigger_bracket_order_gtc_sell,
        preview_trigger_bracket_order_gtd,
        preview_trigger_bracket_order_gtd_buy,
        preview_trigger_bracket_order_gtd_sell,
        stop_limit_order_gtc,
        stop_limit_order_gtc_buy,
        stop_limit_order_gtc_sell,
        stop_limit_order_gtd,
        stop_limit_order_gtd_buy,
        stop_limit_order_gtd_sell,
        trigger_bracket_order_gtc,
        trigger_bracket_order_gtc_buy,
        trigger_bracket_order_gtc_sell,
        trigger_bracket_order_gtd,
        trigger_bracket_order_gtd_buy,
        trigger_bracket_order_gtd_sell,
    )
    from .payments import get_payment_method, list_payment_methods
    from .perpetuals import (
        allocate_portfolio,
        get_perps_portfolio_balances,
        get_perps_portfolio_summary,
        get_perps_position,
        list_perps_positions,
        opt_in_or_out_multi_asset_collateral,
    )
    from .portfolios import (
        create_portfolio,
        delete_portfolio,
        edit_portfolio,
        get_portfolio_breakdown,
        get_portfolios,
        move_portfolio_funds,
    )
    from .products import get_best_bid_ask, get_product, get_product_book, get_products
    from .public import (
        get_public_candles,
        get_public_market_trades,
        get_public_product,
        get_public_product_book,
        get_public_products,
        get_unix_time,
    )
