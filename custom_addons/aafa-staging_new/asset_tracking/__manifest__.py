{
    "name": "Asset Tracking",
    "version": "19.0.1.0.2",
    "summary": "Always Have an Accurate Trace of Your Organization's Assets",
    "category": "Asset Tracking Management",
    "depends": ["hr","account","stock","purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/asset_tracking_view.xml",
        "views/asset_location_view.xml",
        "views/asset_movement_view.xml",
        "views/asset_config_view.xml",
        "data/sequence_view.xml",
    ],
    # "license": "LGPL-3",
    "installable": True,
    "application": True,
}
