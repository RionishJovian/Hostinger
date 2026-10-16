// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listBankAccounts = engineFn("listBankAccounts");
export const saveBankAccount = engineFn("saveBankAccount");
export const notifierStatus = engineFn("notifierStatus");
export const listReceiptReviews = engineFn("listReceiptReviews");
export const getReceiptUrl = engineFn("getReceiptUrl");
export const reviewOrder = engineFn("reviewOrder");
