const { resolveModuleName } = require("ts-pnp")

/**
 * @param {{
 *  resolveModuleName: (
 *    moduleName: string,
 *    containingFile: string,
 *    options: import("typescript").CompilerOptions,
 *    moduleResolutionHost: import("typescript").ModuleResolutionHost
 *  ) => import("typescript").ResolvedTypeReferenceDirectiveWithFailedLookupLocations
 * }} typescript
 * @param {string} moduleName
 * @param {string} containingFile
 * @param {{}} compilerOptions
 * @param {import("typescript").ModuleResolutionHost} resolutionHost
 */
exports.resolveModuleName = (
  typescript,
  moduleName,
  containingFile,
  compilerOptions,
  resolutionHost,
) => {
  return resolveModuleName(
    moduleName,
    containingFile,
    compilerOptions,
    resolutionHost,
    typescript.resolveModuleName,
  )
}

/**
 * @param {{
 *  resolveTypeReferenceDirective: (
 *    moduleName: string,
 *    containingFile: string,
 *    options: import("typescript").CompilerOptions,
 *    moduleResolutionHost: import("typescript").ModuleResolutionHost
 *  ) => import("typescript").ResolvedTypeReferenceDirectiveWithFailedLookupLocations
 * }} typescript
 * @param {string} moduleName
 * @param {string} containingFile
 * @param {{}} compilerOptions
 * @param {import("typescript").ModuleResolutionHost} resolutionHost
 */
exports.resolveTypeReferenceDirective = (
  typescript,
  moduleName,
  containingFile,
  compilerOptions,
  resolutionHost,
) => {
  return resolveModuleName(
    moduleName,
    containingFile,
    compilerOptions,
    resolutionHost,
    typescript.resolveTypeReferenceDirective,
  )
}
