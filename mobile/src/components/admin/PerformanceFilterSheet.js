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

const REVIEW_STATUS = [
  "All",
  "Completed",
  "Pending",
  "In Review",
  "Not Started",
];

const RATINGS = [
  "All",
  "5★",
  "4★ & Above",
  "3★ & Above",
];

const SORT_OPTIONS = [
  "Highest Rating",
  "Lowest Rating",
  "Employee Name",
  "Department",
];

export default function PerformanceFilterSheet({

  visible,

  selectedStatus,

  selectedRating,

  selectedSort,

  onStatusChange,

  onRatingChange,

  onSortChange,

  onReset,

  onApply,

  onClose,

}) {

  return (

    <Modal
      visible={visible}
      animationType="slide"
      transparent
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
              Performance Filters
            </Text>

            <Text style={styles.subtitle}>
              Refine employee performance
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

          {/* ================= STATUS ================= */}

          <Text style={styles.sectionTitle}>
            Review Status
          </Text>

          <View style={styles.optionsContainer}>

            {REVIEW_STATUS.map((item) => {

              const active =
                selectedStatus === item;

              return (

                <TouchableOpacity
                  key={item}
                  activeOpacity={0.9}
                  onPress={() =>
                    onStatusChange(item)
                  }
                  style={[
                    styles.optionChip,
                    active &&
                      styles.activeChip,
                  ]}
                >

                  <Text
                    style={[
                      styles.optionText,
                      active &&
                        styles.activeText,
                    ]}
                  >
                    {item}
                  </Text>

                </TouchableOpacity>

              );

            })}

          </View>

          {/* ================= RATING ================= */}

          <Text style={styles.sectionTitle}>
            Minimum Rating
          </Text>

          <View style={styles.optionsContainer}>

            {RATINGS.map((item) => {

              const active =
                selectedRating === item;

              return (

                <TouchableOpacity
                  key={item}
                  activeOpacity={0.9}
                  onPress={() =>
                    onRatingChange(item)
                  }
                  style={[
                    styles.optionChip,
                    active &&
                      styles.activeChip,
                  ]}
                >

                  <Text
                    style={[
                      styles.optionText,
                      active &&
                        styles.activeText,
                    ]}
                  >
                    {item}
                  </Text>

                </TouchableOpacity>

              );

            })}
                      </View>

          {/* ================= SORT BY ================= */}

          <Text style={styles.sectionTitle}>
            Sort By
          </Text>

          <View style={styles.optionsContainer}>

            {SORT_OPTIONS.map((item) => {

              const active =
                selectedSort === item;

              return (

                <TouchableOpacity
                  key={item}
                  activeOpacity={0.9}
                  onPress={() =>
                    onSortChange(item)
                  }
                  style={[
                    styles.sortCard,
                    active &&
                      styles.activeSortCard,
                  ]}
                >

                  <View
                    style={styles.sortLeft}
                  >

                    <Ionicons
                      name={
                        active
                          ? "radio-button-on"
                          : "radio-button-off"
                      }
                      size={18}
                      color={
                        active
                          ? PERFORMANCE_THEME.colors.primary
                          : PERFORMANCE_THEME.colors.textMuted
                      }
                    />

                    <Text
                      style={[
                        styles.sortText,
                        active &&
                          styles.activeSortText,
                      ]}
                    >
                      {item}
                    </Text>

                  </View>

                  {active && (

                    <Ionicons
                      name="checkmark-circle"
                      size={20}
                      color={
                        PERFORMANCE_THEME.colors.primary
                      }
                    />

                  )}

                </TouchableOpacity>

              );

            })}

          </View>

        </ScrollView>

        {/* ================= ACTION BUTTONS ================= */}

        <View style={styles.footer}>

          <TouchableOpacity
            activeOpacity={0.9}
            style={styles.resetButton}
            onPress={onReset}
          >

            <Ionicons
              name="refresh-outline"
              size={18}
              color={
                PERFORMANCE_THEME.colors.textSecondary
              }
            />

            <Text style={styles.resetText}>
              Reset
            </Text>

          </TouchableOpacity>

          <TouchableOpacity
            activeOpacity={0.9}
            style={styles.applyButton}
            onPress={onApply}
          >

            <Ionicons
              name="checkmark"
              size={18}
              color="#FFFFFF"
            />

            <Text style={styles.applyText}>
              Apply Filters
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

    paddingBottom: 28,

    maxHeight: "88%",
  },

  handle: {
    alignSelf: "center",

    width: 58,

    height: 6,

    borderRadius: 10,

    backgroundColor: "#CBD5E1",

    marginBottom: 22,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 26,
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

  sectionTitle: {
    marginTop: 8,

    marginBottom: 14,

    fontSize: 16,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  optionsContainer: {
    flexDirection: "row",

    flexWrap: "wrap",

    marginBottom: 18,
  },

  optionChip: {
    paddingHorizontal: 16,

    paddingVertical: 11,

    borderRadius: 18,

    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor: "#E2E8F0",

    marginRight: 10,

    marginBottom: 10,
  },

  activeChip: {
    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    borderColor:
      PERFORMANCE_THEME.colors.primary,

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.18,

    shadowRadius: 10,

    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 5,
  },

  optionText: {
    fontSize: 13,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  activeText: {
    color: "#FFFFFF",

    fontWeight: "800",
  },

  sortCard: {
    width: "100%",

    height: 58,

    borderRadius: 18,

    backgroundColor: "#FFFFFF",

    borderWidth: 1,

    borderColor: "#E2E8F0",

    paddingHorizontal: 18,

    marginBottom: 12,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    shadowColor: "#0F172A",

    shadowOpacity: 0.04,

    shadowRadius: 10,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 2,
  },

  activeSortCard: {
    borderColor:
      PERFORMANCE_THEME.colors.primary,

    backgroundColor: "#F8FBFF",
  },

  sortLeft: {
    flexDirection: "row",

    alignItems: "center",
  },

  sortText: {
    marginLeft: 12,

    fontSize: 15,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  activeSortText: {
    color:
      PERFORMANCE_THEME.colors.primary,

    fontWeight: "800",
  },
    footer: {
    flexDirection: "row",

    alignItems: "center",

    justifyContent: "space-between",

    paddingTop: 20,

    marginTop: 8,

    borderTopWidth: 1,

    borderTopColor: "#EEF2F7",
  },

  resetButton: {
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

  resetText: {
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