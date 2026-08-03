import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import LEAVE_THEME from "../../constants/leaveTheme";

export default function LeaveStatusChip({ status = "Pending" }) {
  const getStatus = () => {
    switch (status) {
      case "Approved":
        return {
          color: LEAVE_THEME.colors.success,
          background: LEAVE_THEME.colors.successLight,
          icon: "checkmark-circle",
        };
      case "Rejected":
      case "Declined":
        return {
          color: LEAVE_THEME.colors.danger,
          background: LEAVE_THEME.colors.dangerLight,
          icon: "close-circle",
        };
      case "Cancelled":
        return {
          color: LEAVE_THEME.colors.textMuted,
          background: "#F1F5F9",
          icon: "ban",
        };
      case "Pending":
      default:
        return {
          color: LEAVE_THEME.colors.warning,
          background: LEAVE_THEME.colors.warningLight,
          icon: "time",
        };
    }
  };

  const config = getStatus();

  return (
    <View style={[styles.container, { backgroundColor: config.background }]}>
      <Ionicons name={config.icon} size={14} color={config.color} />
      <Text style={[styles.text, { color: config.color }]}>{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 50,
  },
  text: {
    marginLeft: 6,
    fontSize: 12,
    fontWeight: "700",
  },
});
