"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type AdminCompanyDetail, type AdminCompanyListItem, type AdminDashboard, type AdminPlan,
} from "@/lib/api";

export const useAdminDashboard = () =>
  useQuery({ queryKey: ["admin-dashboard"], queryFn: () => api.get<AdminDashboard>("/admin/dashboard") });

export const useAdminCompanies = (params: { status?: string; q?: string } = {}) => {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status_filter", params.status);
  if (params.q) qs.set("q", params.q);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return useQuery({
    queryKey: ["admin-companies", params],
    queryFn: () => api.get<{ items: AdminCompanyListItem[]; total: number }>(`/admin/companies${suffix}`),
  });
};

export const useAdminCompanyDetail = (id: string | null) =>
  useQuery({
    queryKey: ["admin-company", id],
    queryFn: () => api.get<AdminCompanyDetail>(`/admin/companies/${id}`),
    enabled: !!id,
  });

export function useAdminCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      company_name: string; bin?: string; plan_code: string;
      owner_email: string; owner_name?: string; owner_password: string;
    }) => api.post<{ company_id: string; owner_user_id: string; subscription_id: string }>("/admin/companies", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-companies"] }),
  });
}

export function useAdminChangePlan(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (plan_code: string) =>
      api.post(`/admin/companies/${companyId}/subscription/change-plan`, { plan_code }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-company", companyId] });
      qc.invalidateQueries({ queryKey: ["admin-companies"] });
    },
  });
}

export function useAdminExtendSubscription(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (days: number) =>
      api.post(`/admin/companies/${companyId}/subscription/extend`, { days }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-company", companyId] });
      qc.invalidateQueries({ queryKey: ["admin-companies"] });
    },
  });
}

export function useAdminSuspendSubscription(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/admin/companies/${companyId}/subscription/suspend`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-company", companyId] });
      qc.invalidateQueries({ queryKey: ["admin-companies"] });
    },
  });
}

export function useAdminReactivateSubscription(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/admin/companies/${companyId}/subscription/reactivate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-company", companyId] });
      qc.invalidateQueries({ queryKey: ["admin-companies"] });
    },
  });
}

export function useAdminAddPayment(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { amount: string; currency?: string; comment?: string }) =>
      api.post(`/admin/companies/${companyId}/payments`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-company", companyId] }),
  });
}

export function useAdminCreateUser(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; name?: string; role: string; password: string }) =>
      api.post<{ id: string; email: string }>(`/admin/companies/${companyId}/users`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-company", companyId] }),
  });
}

export function useAdminSetUserActive(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, active }: { userId: string; active: boolean }) =>
      api.patch(`/admin/companies/${companyId}/users/${userId}?active=${active}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-company", companyId] }),
  });
}

export function useAdminResetPassword(companyId: string) {
  return useMutation({
    mutationFn: (userId: string) =>
      api.post<{ id: string; temporary_password: string }>(
        `/admin/companies/${companyId}/users/${userId}/reset-password`,
      ),
  });
}

export const useAdminPlans = () =>
  useQuery({ queryKey: ["admin-plans"], queryFn: () => api.get<AdminPlan[]>("/admin/plans") });

export function useAdminCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<AdminPlan> & { code: string; name: string }) =>
      api.post<AdminPlan>("/admin/plans", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-plans"] }),
  });
}

export function useAdminUpdatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<AdminPlan> & { id: string }) =>
      api.patch<AdminPlan>(`/admin/plans/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-plans"] }),
  });
}

export function useAdminDisablePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/admin/plans/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-plans"] }),
  });
}
