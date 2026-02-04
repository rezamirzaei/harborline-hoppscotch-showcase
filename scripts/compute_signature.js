const crypto = require("crypto");

const args = process.argv.slice(2);
const payloadIndex = args.indexOf("--payload");
const secretIndex = args.indexOf("--secret");

if (payloadIndex === -1 || secretIndex === -1) {
  console.error("Usage: node scripts/compute_signature.js --payload '<json>' --secret '<secret>'");
  process.exit(1);
}

const payload = args[payloadIndex + 1];
const secret = args[secretIndex + 1];

const timestamp = Math.floor(Date.now() / 1000);
const signedPayload = `${timestamp}.${payload}`;
const signature = crypto.createHmac("sha256", secret).update(signedPayload).digest("hex");

console.log(`t=${timestamp},v1=${signature}`);
