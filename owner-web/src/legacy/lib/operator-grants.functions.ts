// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getMyOperatorFeatures = engineFn("getMyOperatorFeatures");
export const listOperatorFeatureGrantsAdmin = engineFn("listOperatorFeatureGrantsAdmin");
export const setOperatorFeatureRoleDefaults = engineFn("setOperatorFeatureRoleDefaults");
export const setOperatorFeatureUserGrants = engineFn("setOperatorFeatureUserGrants");
export const loadResolvedFeatures = engineFn("loadResolvedFeatures");
export const assertCanOperateFeature = engineFn("assertCanOperateFeature");
