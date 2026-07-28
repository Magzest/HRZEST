import React from "react";

import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceActionSheet({

  visible,

  employeeName,

  onView,

  onEdit,

  onApprove,

  onReject,

  onShare,

  onExport,

  onClose,

}) {

  const actions = [

    {
      title: "View Review",
      subtitle: "Open complete review details",

      icon: "eye-outline",

      color: "#2563EB",

      background: "#DBEAFE",

      onPress: onView,
    },

    {
      title: "Edit Review",
      subtitle: "Modify employee review",

      icon: "create-outline",

      color: "#F59E0B",

      background: "#FEF3C7",

      onPress: onEdit,
    },

    {
      title: "Approve Review",
      subtitle: "Mark review as approved",

      icon: "checkmark-circle-outline",

      color: "#10B981",

      background: "#DCFCE7",

      onPress: onApprove,
    },

    {
      title: "Reject Review",
      subtitle: "Reject this submission",

      icon: "close-circle-outline",

      color: "#EF4444",

      background: "#FEE2E2",

      onPress: onReject,
    },

    {
      title: "Share Review",

      subtitle: "Share performance summary",

      icon: "share-social-outline",

      color: "#7C3AED",

      background: "#F3E8FF",

      onPress: onShare,
    },

    {
      title: "Export PDF",

      subtitle: "Generate review report",

      icon: "document-text-outline",

      color: "#0EA5E9",

      background: "#E0F2FE",

      onPress: onExport,
    },

  ];

  return (

    <Modal
      transparent
      animationType="slide"
      visible={visible}
    >

      <TouchableOpacity
        activeOpacity={1}
        style={styles.overlay}
        onPress={onClose}
      />

      <View style={styles.sheet}>

        {/* Handle */}

        <View style={styles.handle} />

        {/* Header */}

        <View style={styles.header}>

          <View>

            <Text style={styles.title}>
              Employee Actions
            </Text>

            <Text style={styles.subtitle}>
              {employeeName}
            </Text>

          </View>

          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
          >

            <Ionicons
              name="close"
              size={22}
              color={
                PERFORMANCE_THEME.colors.textPrimary
              }
            />

          </TouchableOpacity>

        </View>

        {/* Action List */}
                {actions.map((item) => (

          <TouchableOpacity
            key={item.title}
            activeOpacity={0.88}
            style={styles.actionCard}
            onPress={() => {

              item.onPress?.();

              onClose?.();

            }}
          >

            <View style={styles.leftSection}>

              <View
                style={[
                  styles.iconContainer,
                  {
                    backgroundColor:
                      item.background,
                  },
                ]}
              >

                <Ionicons
                  name={item.icon}
                  size={22}
                  color={item.color}
                />

              </View>

              <View style={styles.content}>

                <Text style={styles.actionTitle}>
                  {item.title}
                </Text>

                <Text style={styles.actionSubtitle}>
                  {item.subtitle}
                </Text>

              </View>

            </View>

            <Ionicons
              name="chevron-forward"
              size={20}
              color={
                PERFORMANCE_THEME.colors.textLight
              }
            />

          </TouchableOpacity>

        ))}

        {/* ================= CANCEL ================= */}

        <TouchableOpacity
          activeOpacity={0.9}
          style={styles.cancelButton}
          onPress={onClose}
        >

          <Ionicons
            name="close-outline"
            size={20}
            color={
              PERFORMANCE_THEME.colors.textSecondary
            }
          />

          <Text style={styles.cancelText}>
            Close
          </Text>

        </TouchableOpacity>

      </View>

    </Modal>

  );

}
const styles = StyleSheet.create({

  overlay: {
    flex: 1,

    backgroundColor: "rgba(15,23,42,0.45)",

    justifyContent: "flex-end",
  },

  sheet: {
    backgroundColor: "#FFFFFF",

    borderTopLeftRadius: 34,

    borderTopRightRadius: 34,

    paddingHorizontal: 24,

    paddingTop: 16,

    paddingBottom: 28,

    maxHeight: "90%",
  },

  handle: {
    alignSelf: "center",

    width: 60,

    height: 6,

    borderRadius: 10,

    backgroundColor: "#CBD5E1",

    marginBottom: 22,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 22,
  },

  title: {
    fontSize: 24,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 5,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  closeButton: {
    width: 46,

    height: 46,

    borderRadius: 16,

    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor: "#EEF2F7",

    justifyContent: "center",

    alignItems: "center",
  },

  actionCard: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingHorizontal: 18,

    paddingVertical: 16,

    marginBottom: 14,

    borderWidth: 1,

    borderColor: "#EEF2F7",

    shadowColor: "#0F172A",

    shadowOpacity: 0.04,

    shadowRadius: 10,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 2,
  },

  leftSection: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  iconContainer: {
    width: 54,

    height: 54,

    borderRadius: 18,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  content: {
    flex: 1,
  },

  actionTitle: {
    fontSize: 16,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  actionSubtitle: {
    marginTop: 4,

    fontSize: 13,

    lineHeight: 18,

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },
    cancelButton: {
    marginTop: 10,

    height: 58,

    borderRadius: 18,

    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor: "#E2E8F0",

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    shadowColor: "#0F172A",

    shadowOpacity: 0.03,

    shadowRadius: 8,

    shadowOffset: {
      width: 0,
      height: 3,
    },

    elevation: 2,
  },

  cancelText: {
    marginLeft: 8,

    fontSize: 15,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

});