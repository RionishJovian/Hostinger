// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listMyNotifications = engineFn("listMyNotifications");
export const markNotificationRead = engineFn("markNotificationRead");
export const markAllNotificationsRead = engineFn("markAllNotificationsRead");
export const deleteNotification = engineFn("deleteNotification");
export const deleteReadNotifications = engineFn("deleteReadNotifications");
