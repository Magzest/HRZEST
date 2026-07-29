<<<<<<< HEAD
import React from "react";

import {
  createDrawerNavigator,
} from "@react-navigation/drawer";

import AdminBottomNavigator from "./AdminBottomNavigator";

import AdminDrawerContent from "../screens/admin/AdminDrawerContent";

import THEME from "../constants/theme";

const Drawer = createDrawerNavigator();

export default function AdminDrawerNavigator() {
  return (
    <Drawer.Navigator
      initialRouteName="AdminTabs"
      drawerContent={(props) => (
        <AdminDrawerContent {...props} />
      )}
      screenOptions={{
        headerShown: false,

        drawerType: "slide",

        drawerPosition: "left",

        swipeEnabled: true,

        overlayColor: "rgba(15,23,42,0.25)",

        drawerStyle: {
          width: 320,

          backgroundColor:
            THEME.colors.background,

          borderTopRightRadius: 28,

          borderBottomRightRadius: 28,
        },

        sceneContainerStyle: {
          backgroundColor:
            THEME.colors.background,
        },
      }}
    >
      <Drawer.Screen
        name="AdminTabs"
        component={AdminBottomNavigator}
      />
    </Drawer.Navigator>
  );
}
=======
import React from "react";

import {
  createDrawerNavigator,
} from "@react-navigation/drawer";

import AdminBottomNavigator from "./AdminBottomNavigator";

import AdminDrawerContent from "../screens/admin/AdminDrawerContent";

import THEME from "../constants/theme";

const Drawer = createDrawerNavigator();

export default function AdminDrawerNavigator() {
  return (
    <Drawer.Navigator
      initialRouteName="AdminTabs"
      drawerContent={(props) => (
        <AdminDrawerContent {...props} />
      )}
      screenOptions={{
        headerShown: false,

        drawerType: "slide",

        drawerPosition: "left",

        swipeEnabled: true,

        overlayColor: "rgba(15,23,42,0.25)",

        drawerStyle: {
          width: 320,

          backgroundColor:
            THEME.colors.background,

          borderTopRightRadius: 28,

          borderBottomRightRadius: 28,
        },

        sceneContainerStyle: {
          backgroundColor:
            THEME.colors.background,
        },
      }}
    >
      <Drawer.Screen
        name="AdminTabs"
        component={AdminBottomNavigator}
      />
    </Drawer.Navigator>
  );
}
>>>>>>> 6dbd917e (Update admin attendance and payroll screens)
