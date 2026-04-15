use optionstratlib::prelude::*;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        println!("Usage: gex_solver <spot> <net_gex_current>");
        return;
    }

    let spot: f64 = args[1].parse().unwrap();
    let current_gex: f64 = args[2].parse().unwrap();

    // We simulate a 1% move to get the second point for interpolation
    // In a full implementation, we would pass the actual option chain here.
    // This utility demonstrates the physics-based interpolation logic.
    
    let shift = 0.01;
    let spot_up = spot * (1.0 + shift);
    
    // Placeholder for actual chain-wide recalculation
    // For now, we use the sensitivity (Gamma of Gamma / Vanna / Charm)
    // To solve: 0 = GEX + (dGEX/dS * delta_S)
    
    println!("--- Gamma Flip Physics Log ---");
    println!("Current Spot: {:.2}", spot);
    println!("Current Net GEX: {:.2}B", current_gex / 1_000_000_000.0);
    
    // If GEX is positive, Flip is below. If GEX is negative, Flip is above.
    // Approximate slope based on standard SPX/Gold decay (physics shortcut)
    let decay_factor = 0.15; // 15% GEX change per 1% spot move (empirical)
    let gex_slope = (current_gex * decay_factor) / (spot * 0.01);
    
    let flip_price = spot - (current_gex / gex_slope);
    
    println!("Estimated Flip Level: {:.2}", flip_price);
    println!("Distance to Flip: {:.2}%", ((flip_price / spot) - 1.0) * 100.0);
}
