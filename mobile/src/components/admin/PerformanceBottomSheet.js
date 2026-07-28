import React from "react";

import {
  Modal,
  View,
 Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceBottomSheet({

  visible,

  title = "Select Department",

  options = [],

  selected,

  onSelect,

  onClose,

}) {

  return (

    <Modal
      transparent
      visible={visible}
      animationType="slide"
    >

      <TouchableOpacity
        style={styles.overlay}
        activeOpacity={1}
        onPress={onClose}
      />

      <View style={styles.sheet}>

        {/* Handle */}

        <View style={styles.handle} />

        {/* Header */}

        <View style={styles.header}>

          <View>

            <Text style={styles.title}>
              {title}
            </Text>

            <Text style={styles.subtitle}>
              Choose one option
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

        <ScrollView
          showsVerticalScrollIndicator={false}
        >

          {options.map((item) => {

            const active =
              item === selected;

            return (

              <TouchableOpacity
                key={item}
                activeOpacity={0.9}
                onPress={() =>
                  onSelect(item)
                }
                style={[
                  styles.optionCard,
                  active &&
                    styles.activeCard,
                ]}
              >

                <View
                  style={styles.optionLeft}
                >

                  <View
                    style={[
                      styles.iconContainer,
                      active && {
                        backgroundColor:
                          PERFORMANCE_THEME.colors.primary,
                      },
                    ]}
                  >

                    <Ionicons
                      name="business-outline"
                      size={20}
                      color={
                        active
                          ? "#FFFFFF"
                          : PERFORMANCE_THEME.colors.primary
                      }
                    />

                  </View>

                  <View>

                    <Text
                      style={[
                        styles.optionTitle,
                        active &&
                          styles.activeTitle,
                      ]}
                    >
                      {item}
                    </Text>

                    <Text
                      style={
                        styles.optionSubtitle
                      }
                    >
                      Performance Department
                    </Text>

                  </View>

                </View>

                <Ionicons
                  name={
                    active
                      ? "checkmark-circle"
                      : "chevron-forward"
                  }
                  size={22}
                  color={
                    active
                      ? PERFORMANCE_THEME.colors.primary
                      : PERFORMANCE_THEME.colors.textLight
                  }
                />

              </TouchableOpacity>

            );

          })}
                  </ScrollView>

        {/* ================= ACTION BUTTONS ================= */}

        <View style={styles.footer}>

          <TouchableOpacity
            activeOpacity={0.9}
            style={styles.cancelButton}
            onPress={onClose}
          >

            <Ionicons
              name="close-outline"
              size={18}
              color={
                PERFORMANCE_THEME.colors.textSecondary
              }
            />

            <Text style={styles.cancelText}>
              Cancel
            </Text>

          </TouchableOpacity>

          <TouchableOpacity
            activeOpacity={0.9}
            style={styles.applyButton}
            onPress={onClose}
          >

            <Ionicons
              name="checkmark-outline"
              size={18}
              color="#FFFFFF"
            />

            <Text style={styles.applyText}>
              Apply Selection
            </Text>

          </TouchableOpacity>

        </View>

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

    paddingBottom: 26,

    maxHeight: "88%",
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

    marginBottom: 24,
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

    justifyContent: "center",

    alignItems: "center",

    borderWidth: 1,

    borderColor: "#EEF2F7",
  },

  optionCard: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingHorizontal: 18,

    paddingVertical: 16,

    marginBottom: 14,

    borderWidth: 1,

    borderColor: "#E2E8F0",

    shadowColor: "#0F172A",

    shadowOpacity: 0.04,

    shadowRadius: 10,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 2,
  },

  activeCard: {
    backgroundColor: "#F8FBFF",

    borderColor:
      PERFORMANCE_THEME.colors.primary,

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.12,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 5,
  },

  optionLeft: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  iconContainer: {
    width: 52,

    height: 52,

    borderRadius: 16,

    backgroundColor:
      PERFORMANCE_THEME.colors.primaryLight,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  optionTitle: {
    fontSize: 16,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  activeTitle: {
    color:
      PERFORMANCE_THEME.colors.primary,
  },

  optionSubtitle: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },
    footer: {
    flexDirection: "row",

    alignItems: "center",

    justifyContent: "space-between",

    marginTop: 12,

    paddingTop: 20,

    borderTopWidth: 1,

    borderTopColor: "#EEF2F7",
  },

  cancelButton: {
    flex: 1,

    height: 56,

    marginRight: 10,

    borderRadius: 18,

    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor: "#E2E8F0",

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",
  },

  cancelText: {
    marginLeft: 8,

    fontSize: 15,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  applyButton: {
    flex: 2,

    height: 56,

    borderRadius: 18,

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.22,

    shadowRadius: 14,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 8,
  },

  applyText: {
    marginLeft: 8,

    fontSize: 15,

    fontWeight: "800",

    color: "#FFFFFF",
  },

});