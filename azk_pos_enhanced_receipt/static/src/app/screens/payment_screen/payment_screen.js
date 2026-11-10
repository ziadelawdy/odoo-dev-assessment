import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AzkReceiptPreview } from "@azk_pos_enhanced_receipt/app/components/receipt_preview/receipt_preview";

PaymentScreen.components = { ...PaymentScreen.components, AzkReceiptPreview };
