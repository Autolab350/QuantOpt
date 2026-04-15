/// Re-export of `ExpirationDate` from the standalone `expiration_date` crate.
///
/// This module re-exports the `ExpirationDate` enum and its error type from the
/// external `expiration_date` crate, which provides all the core functionality
/// for handling financial instrument expiration dates.
pub use expiration_date::ExpirationDate;
pub use expiration_date::error::ExpirationDateError;
