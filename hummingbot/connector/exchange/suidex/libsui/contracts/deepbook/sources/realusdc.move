module deepbook::realusdc{
    use std::option;
    use sui::coin::{Self};
    use sui::transfer;
    use sui::tx_context::{Self, TxContext};

    public struct REALUSDC has drop {}

    #[allow(unused_function)]
    fun init(witness: REALUSDC, ctx: &mut TxContext) {
        let (treasury, metadata) = coin::create_currency(witness, 6, b"REALUSDC", b"Real USDC", b"Mocked Version of a real USDC", option::none(), ctx);
        transfer::public_freeze_object(metadata);
        transfer::public_transfer(treasury, tx_context::sender(ctx))
    }
    
}