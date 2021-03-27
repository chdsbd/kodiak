const jwt = require("jsonwebtoken")

/** @returns {string | null} */
function generateSignedUrl() {
  if (!process.env.DEPLOY_PRIME_URL || !process.env.KODIAK_DEPLOY_URL_SECRET) {
    return null
  }
  return jwt.sign(
    { url: process.env.DEPLOY_PRIME_URL },
    process.env.KODIAK_DEPLOY_URL_SECRET,
    {
      algorithm: "HS256",
    },
  )
}

module.exports = { generateSignedUrl }
