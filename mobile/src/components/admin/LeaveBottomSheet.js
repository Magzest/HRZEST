import React from "react";

import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import LEAVE_THEME from "../../constants/leaveTheme";
import LeaveStatusChip from "./LeaveStatusChip";

export default function LeaveBottomSheet({
  visible,
  leave,
  onApprove,
  onReject,
  onClose,
}) {
  if (!leave) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.sheet}>

          <View style={styles.handle} />

          <View style={styles.header}>
            <Text style={styles.title}>
              Leave Details
            </Text>

            <TouchableOpacity onPress={onClose}>
              <Ionicons
                name="close"
                size={24}
                color={LEAVE_THEME.colors.textPrimary}
              />
            </TouchableOpacity>
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
          >

            <View style={styles.employeeCard}>
              <View style={styles.avatar}>
                <Ionicons
                  name="person"
                  size={28}
                  color={LEAVE_THEME.colors.primary}
                />
              </View>

              <View style={styles.info}>
                <Text style={styles.name}>
                  {leave.employeeName}
                </Text>

                <Text style={styles.sub}>
                  {leave.employeeId}
                </Text>

                <Text style={styles.sub}>
                  {leave.department}
                </Text>
              </View>

              <LeaveStatusChip
                status={leave.status}
              />
            </View>

            <View style={styles.card}>
              <Text style={styles.label}>
                Leave Type
              </Text>

              <Text style={styles.value}>
                {leave.leaveType}
              </Text>
            </View>

            <View style={styles.row}>
              <View style={styles.smallCard}>
                <Text style={styles.label}>
                  From
                </Text>

                <Text style={styles.value}>
                  {leave.startDate}
                </Text>
              </View>

              <View style={styles.smallCard}>
                <Text style={styles.label}>
                  To
                </Text>

                <Text style={styles.value}>
                  {leave.endDate}
                </Text>
              </View>
            </View>

            <View style={styles.card}>
              <Text style={styles.label}>
                Duration
              </Text>

              <Text style={styles.value}>
                {leave.days} Days
              </Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.label}>
                Reason
              </Text>

              <Text style={styles.reason}>
                {leave.reason}
              </Text>
            </View>

          </ScrollView>

          <View style={styles.footer}>

            <TouchableOpacity
              style={styles.rejectButton}
              onPress={() => onReject(leave)}
            >
              <Ionicons
                name="close"
                size={18}
                color="#DC2626"
              />

              <Text style={styles.rejectText}>
                Reject
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.approveButton}
              onPress={() => onApprove(leave)}
            >
              <Ionicons
                name="checkmark"
                size={18}
                color="#FFFFFF"
              />

              <Text style={styles.approveText}>
                Approve
              </Text>
            </TouchableOpacity>

          </View>

        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({

  overlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.35)",
  },

  sheet: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 20,
    maxHeight: "85%",
  },

  handle: {
    width: 60,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#CBD5E1",
    alignSelf: "center",
    marginBottom: 20,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },

  title: {
    fontSize: 22,
    fontWeight: "800",
    color: LEAVE_THEME.colors.textPrimary,
  },

  employeeCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    padding: 16,
    marginBottom: 18,
  },

  avatar: {
    width: 56,
    height: 56,
    borderRadius: 18,
    backgroundColor: LEAVE_THEME.colors.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },

  info: {
    flex: 1,
    marginLeft: 14,
  },

  name: {
    fontSize: 16,
    fontWeight: "700",
    color: LEAVE_THEME.colors.textPrimary,
  },

  sub: {
    fontSize: 13,
    color: LEAVE_THEME.colors.textMuted,
    marginTop: 2,
  },

  card: {
    backgroundColor: "#F8FAFC",
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },

  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 16,
  },

  smallCard: {
    width: "48%",
    backgroundColor: "#F8FAFC",
    borderRadius: 16,
    padding: 16,
  },

  label: {
    fontSize: 12,
    color: LEAVE_THEME.colors.textMuted,
  },

  value: {
    marginTop: 6,
    fontSize: 15,
    fontWeight: "700",
    color: LEAVE_THEME.colors.textPrimary,
  },

  reason: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 22,
    color: LEAVE_THEME.colors.textSecondary,
  },

  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 12,
  },

  rejectButton: {
    width: "48%",
    height: 52,
    borderRadius: 16,
    backgroundColor: "#FEE2E2",
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
  },

  rejectText: {
    marginLeft: 8,
    color: "#DC2626",
    fontWeight: "700",
  },

  approveButton: {
    width: "48%",
    height: 52,
    borderRadius: 16,
    backgroundColor: "#16A34A",
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
  },

  approveText: {
    marginLeft: 8,
    color: "#FFFFFF",
    fontWeight: "700",
  },

});