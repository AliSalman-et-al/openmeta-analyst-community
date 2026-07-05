#############################################################################
#                                                                           #
#  Byron C. Wallace                                                         #
#  George Dietz                                                             #
#  CEBM @ Brown                                                             #
#  OpenMeta[analyst]                                                        #
#                                                                           #
#  This is a proxy module that is responsible for communicating with R.     #
#  An unholy mixture of R and Python                                        #
#   **All calls to R (equivalently, all references to the rpy2 library)     #
#   are to be made via this module **                                       #
#                                                                           #
#############################################################################

print("Entering meta_py_r for import probably")
import math
import os
import re
import r_runtime
from analysis_method_labels import (
    method_display_label,
    normalize_available_method_labels,
)
import result_sections
from study_effect_shapes import (
    effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)
from r_call_serialization import serialized_r_call
from meta_globals import *

r_runtime.configure_bundled_r_environment()
print(("the path: %s" % os.getenv("PATH")))

try:
    print("importing from rpy2")
    # will fail if not properly configured
    # good place to debug when trying to get the mac build to work
    # from rpy2 import robjects as ro
    import rpy2.robjects as ro

    print("succesfully imported from rpy2")
except Exception as e:
    print(e)
    print("rpy2 import problem")
    # pyqtRemoveInputHook()
    # pdb.set_trace()
    raise Exception("rpy2 not properly installed!")
    print(e)
print("importing rpy2.robjects")
import rpy2.robjects
import rpy2.rinterface

print("succesfully imported rpy2.robjects")

try:
    import rpy2.rinterface_lib.conversion as _rpy2_conversion

    _rpy2_rchar_to_str = _rpy2_conversion._rchar_to_str

    def _rchar_to_str_as_utf8(rchar, encoding):
        try:
            return _rpy2_conversion._utf8_rchar_to_str(rchar)
        except UnicodeDecodeError:
            return _rpy2_rchar_to_str(rchar, encoding)

    _rpy2_conversion._rchar_to_str = _rchar_to_str_as_utf8
except Exception:
    pass


def _r_is_null(r_object):
    """True if an rpy2 object is R's NULL.

    rpy2 >= 3.x represents NULL as a ``NULLType`` singleton whose ``str()`` is
    an object repr (e.g. ``<rpy2...NULLType object at 0x...>``), not the literal
    ``"NULL"`` that the legacy Python-2 rpy2 produced. Code that detected NULL
    via ``str(x) == "NULL"`` therefore silently misfires (e.g. treating a list
    with NULL names as if it had names). Prefer identity/type checks and fall
    back to the legacy string compare for older rpy2 builds."""
    try:
        if r_object is rpy2.rinterface.NULL:
            return True
        if isinstance(r_object, type(rpy2.rinterface.NULL)):
            return True
    except Exception:
        pass
    return str(r_object) == "NULL"


@serialized_r_call
def execute_r_string(r_str):

    try:
        print(("Executing: %s\n" % r_str))
        return ro.r(r_str)
    except Exception as e:
        # reset working directory in r then raise the error, hope this will address issue #244
        print("something bad happened in R")
        reset_Rs_working_dir()
        raise e


@serialized_r_call
def execute_r_function(function_name, *args, **kwargs):
    return ro.r[function_name](*args, **kwargs)


#################### R Library Loader ####################
class RlibLoader:
    def __init__(self):
        print("R Libary loader (RlibLoader) initialized...")

    def load_metafor(self):
        return self._load_r_lib("metafor")

    def load_OpenMetaR(self):
        return self._load_r_lib("OpenMetaR")

    def load_igraph(self):
        return self._load_r_lib("igraph")

    def load_grid(self):
        return self._load_r_lib("grid")

    def load_gemtc(self):
        return self._load_r_lib("gemtc")

    def load_all(self):
        self.load_metafor()
        self.load_OpenMetaR()
        self.load_igraph()
        self.load_grid()
        self.load_gemtc()

    def _load_r_lib(self, name):
        try:
            execute_r_function("library", name)
            msg = "%s package successfully loaded" % name
            print(msg)
            return (True, msg)
        except:
            raise Exception(
                "The %s R package is not installed.\nPlease \
install this package and then re-start OpenMeta."
                % name
            )


#################### END OF R Library Loader ####################


def RfunctionCaller(function):
    @serialized_r_call
    def _RfunctionCaller(*args, **kw):
        print(("Using rpy2 interface to R to call %s" % function.__name__))
        res = function(*args, **kw)
        return res

    return _RfunctionCaller


def get_R_libpaths():
    """Returns the libpaths that R looks at, sanity check to make sure it sees the right paths"""

    libpaths = execute_r_string(".libPaths()")
    print("R Lib paths:")
    for i, path in enumerate(libpaths):
        print(("%d: %s" % (i, path)))
    return list(libpaths)


@RfunctionCaller
def get_r_version_string():
    return str(execute_r_string("R.version.string")[0])


@RfunctionCaller
def get_r_package_version(package_name):
    version = execute_r_function("packageVersion", package_name)
    return str(execute_r_function("as.character", version)[0])


@RfunctionCaller
def reset_Rs_working_dir():
    """resets R's working directory to the the application base_path, not to r_tmp!"""
    print("resetting R working dir")

    # Fix paths issue in windows
    import settings

    base_path = settings.get_base_path()
    base_path = settings.to_posix_path(base_path)

    print(("Trying to set base_path to %s" % base_path))
    execute_r_function("setwd", base_path)

    print(("Set R's working directory to %s" % base_path))


@RfunctionCaller
def impute_diag_data(diag_data_dict):
    print("computing 2x2 table via R...")
    print(diag_data_dict)
    diag_data_dict = normalize_confidence_level_params(diag_data_dict)

    # rpy2 doesn't know how to handle None types.
    # we can just remove them from the dictionary.
    for param, val in list(diag_data_dict.items()):
        if val is None:
            diag_data_dict.pop(param)

    dataf = ro.r["data.frame"](**diag_data_dict)
    two_by_two = execute_r_function("openmetar.impute.diagnostic", dataf)

    imputed_2x2 = R_parse_tools.rlist_to_pydict(two_by_two)
    print(("Imputed 2x2: %s" % str(imputed_2x2)))

    return imputed_2x2


@RfunctionCaller
def impute_bin_data(bin_data_dict):
    bin_data_dict = normalize_confidence_level_params(bin_data_dict)
    remove_value(None, bin_data_dict)

    dataf = ro.r["data.frame"](**bin_data_dict)
    two_by_two = execute_r_function("openmetar.impute.binary", dataf)

    res_as_dict = R_parse_tools.recursioner(two_by_two)

    return res_as_dict


@RfunctionCaller
def back_calc_cont_data(group1_data, group2_data, effect_data, conf_level):
    conf_level = validate_confidence_level(conf_level)
    remove_value(None, group1_data)
    remove_value(None, group2_data)
    remove_value(None, effect_data)

    dataf_grp1 = ro.r["data.frame"](**group1_data)
    dataf_grp2 = ro.r["data.frame"](**group2_data)
    dataf_effect = ro.r["data.frame"](**effect_data)

    r_res = execute_r_function(
        "openmetar.back.calculate.continuous",
        dataf_grp1,
        dataf_grp2,
        dataf_effect,
        conf_level,
    )

    res_as_dict = R_parse_tools.recursioner(r_res)

    return res_as_dict


def remove_value(toRemove, t_dict):
    """Removes all entries in t_dict with value toRemove"""
    for param, val in list(t_dict.items()):
        if val == toRemove:
            t_dict.pop(param)


def _gis_NA(x):
    return str(x) == "NA"


###### R data structure tools #############


class R_parse_tools:
    """a set of tools to help parse data structures returned from rpy2"""

    def __init__(self):
        pass

    @staticmethod
    def rlist_to_pydict(named_r_list):
        """parse named R list into a python dictionary."""
        # Only parses one level, is not recursive.'''

        keys = named_r_list.names
        if _r_is_null(keys):
            raise ValueError("No names found in alleged named R list")

        data = R_parse_tools.R_iterable_to_pylist(named_r_list)
        d = dict(list(zip(keys, data)))

        return d

    @staticmethod
    def recursioner(data):
        """
        named_r_list --> python dictionary
        not named r_list --> python list
               singleton_r_list ---> python scalar
        """

        if R_parse_tools.haskeys(data):  # can be converted to dictionary
            d = R_parse_tools.rlist_to_pydict(data)
            for k, v in list(d.items()):
                d[k] = R_parse_tools.recursioner(v)
            return d
        elif R_parse_tools._isListable(data):  # can be converted to list
            l = R_parse_tools.R_iterable_to_pylist(data)
            for i, v in enumerate(l):
                l[i] = R_parse_tools.recursioner(v)
            return l
        else:  # is a scalar
            return R_parse_tools._convert_NA_to_None(data)  # convert NA to None

    @staticmethod
    def R_iterable_to_pylist(r_iterable):
        """Converts an r_iterable (i.e. list or vector) to a python list.
        Will convert singleton elements to scalars in the list but not the list
        itself if it is singleton."""

        def filter_list_element(x):
            """if x is a singleton list, converts x to a scalar"""
            if R_parse_tools._isListable(x) and len(x) == 1:
                return R_parse_tools._singleton_list_to_scalar(x)
            else:
                return x

        python_list = list(r_iterable)
        python_list = [filter_list_element(x) for x in python_list]
        return python_list

    @staticmethod
    def _singleton_list_to_scalar(singleton_list):
        """Takes in a singleton R list and returns a scalar value and converts 'NA'
        to None"""

        if len(singleton_list) > 1:
            raise ValueError(
                "Expected a singleton list but this list has more than one entry"
            )

        # special case of a factor ve
        if type(singleton_list) == rpy2.robjects.vectors.FactorVector:
            return execute_r_function("as.character", singleton_list)[0]

        scalar = singleton_list[0]
        return R_parse_tools._convert_NA_to_None(scalar)

    @staticmethod
    def _convert_NA_to_None(scalar):
        if str(scalar) == "NA":
            return None
        else:
            return scalar

    @staticmethod
    def _isListable(element, exclude_strings=True):
        try:
            list(element)
        except TypeError:
            return False

        # don't want to treat strings as lists even though they are iterable
        if exclude_strings and type(element) == str:
            return False

        return True

    @staticmethod
    def haskeys(r_object):
        if not hasattr(r_object, "names"):
            return False

        return not _r_is_null(r_object.names)


#### end of R data structure tools #########


# This should be renamed as it is not doing back-calculation from effects
@RfunctionCaller
def impute_cont_data(cont_data_dict, alpha):
    print("computing continuous data via R...")

    # first check that we have some data;
    # if not, there's no sense in trying to
    # impute anything
    if len(list(cont_data_dict.items())) == 0:
        return {"succeeded": False}

    dataf = ro.r["data.frame"](**cont_data_dict)
    c_data = execute_r_function("openmetar.impute.continuous.study", dataf, alpha=alpha)

    results = R_parse_tools.recursioner(c_data)

    return results


@RfunctionCaller
def impute_pre_post_cont_data(cont_data_dict, correlation, alpha):
    if len(list(cont_data_dict.items())) == 0:
        return {"succeeded": False}

    dataf = ro.r["data.frame"](**cont_data_dict)
    c_data = execute_r_function(
        "openmetar.impute.continuous.prepost",
        dataf,
        correlation=correlation,
        alpha=alpha,
    )
    pythonized_data = R_parse_tools.recursioner(c_data)

    return pythonized_data


##################### DEALING WITH CONFIDENCE LEVEL IN R #######################
@RfunctionCaller
def get_mult_from_r(confidence_level):
    confidence_level = validate_confidence_level(confidence_level)
    alpha = 1 - float(confidence_level) / 100.0
    mult = execute_r_function("openmetar.get.mult.from.conf.level", confidence_level)
    multiplier = float(mult[0])
    if not math.isfinite(multiplier):
        raise ValueError(INVALID_CONFIDENCE_LEVEL_MESSAGE)
    return multiplier


@RfunctionCaller
def set_global_conf_level(confidence_level):
    confidence_level = validate_confidence_level(confidence_level)
    new_level = execute_r_function(
        "openmetar.set.global.conf.level", float(confidence_level)
    )
    return float(new_level[0])


################################################################################


@RfunctionCaller
def none_to_null(x):
    if x is None:
        return rpy2.rinterface.NULL
    return x


def _r_null_if_none(value):
    return rpy2.rinterface.NULL if value is None else value


def get_params(method_name):
    param_list = execute_r_function("openmetar.method.parameters", str(method_name))
    param_d = {}
    for name, r_obj in zip(param_list.names, param_list):
        param_d[name] = r_obj

    order_vars = None
    if "var_order" in param_d:
        order_vars = list(param_d["var_order"])

    pretty_names_and_descriptions = R_parse_tools.recursioner(
        param_d.get("pretty.names", ro.r["list"]())
    )

    return (
        R_parse_tools.recursioner(param_d["parameters"]),
        R_parse_tools.recursioner(param_d["defaults"]),
        order_vars,
        pretty_names_and_descriptions,
    )


@RfunctionCaller
def get_pretty_names_and_descriptions_for_params(method_name, param_list):
    params_d = R_parse_tools.recursioner(
        execute_r_function("openmetar.method.parameters", str(method_name)).rx2(
            "pretty.names"
        )
    )

    # fill in entries for parameters for which pretty names/descriptions were
    # not provided-- these are just place-holders to make processing this
    # easier
    names_index = param_list.names.index("parameters")
    param_names = param_list[names_index].names  # pull out the list
    for param in param_names:
        if not param in list(params_d.keys()):
            params_d[param] = {"pretty.name": param, "description": "None provided"}

    return params_d


@RfunctionCaller
def get_available_methods(for_data_type=None, data_obj_name=None, metric=None):
    """
    Returns a list of methods available in OpenMeta for the particular data_type
    (if one is given).
    """
    data_arg = None if data_obj_name is None else ro.globalenv[str(data_obj_name)]
    methods = execute_r_function(
        "openmetar.available.methods",
        **{
            "data.type": _r_null_if_none(
                None if for_data_type is None else str(for_data_type)
            ),
            "om.data": _r_null_if_none(data_arg),
            "metric": _r_null_if_none(None if metric is None else str(metric)),
        },
    )
    return normalize_available_method_labels(R_parse_tools.recursioner(methods))


@RfunctionCaller
def get_method_description(method_name):
    return execute_r_function("openmetar.method.description", str(method_name))[0]


# def ma_dataset_to_binary_robj(table_model, var_name):
#    pass


@RfunctionCaller
def draw_network(edge_list, unconnected_vertices, network_path='"./r_tmp/network.png"'):
    """
    This draws the parametric network specified by edge_list.
    The latter is assumed to be in form:
        ["tx a", "tx b", "tx b", "tx c" .... "tx z']
    Where two adjacent entires in the list are connected.
    Note that we (lazily) make all calls to R here rather than
    implementing a method on the R side that takes a graph/
    edge list. We may want to change this eventually.
    """
    network_path = _strip_wrapping_quotes(network_path)
    if len(edge_list) > 0:
        edge_matrix = execute_r_function(
            "matrix", _r_character_vector(edge_list), ncol=2, byrow=True
        )
        graph = execute_r_function("graph.edgelist", edge_matrix, directed=False)
    else:
        graph = execute_r_function("graph.empty")

    if len(unconnected_vertices) > 0:
        print(unconnected_vertices)
        graph = execute_r_function(
            "add.vertices",
            graph,
            len(unconnected_vertices),
            name=_r_character_vector(unconnected_vertices),
        )
    ro.globalenv["g"] = graph
    execute_r_function("png", network_path)
    execute_r_string(
        "plot(g, vertex.label=V(g)$name, layout=layout.circle, vertex.size=25, asp=.3, margin=-.05)"
    )
    execute_r_string("dev.off()")
    return "r_tmp/network.png"


@RfunctionCaller
def ma_dataset_to_simple_continuous_robj(
    table_model, var_name="tmp_obj", covs_to_include=None, studies=None
):
    if studies is None:
        # grab all studies. note: the list is pulled out in reverse order from the
        # model, so we, er, reverse it.
        studies = table_model.get_studies()
    # the study_ids preserve the ordering
    study_ids = [study.id for study in studies]

    ests, SEs = table_model.get_cur_ests_and_SEs(only_these_studies=study_ids)

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=ests,
        SE=SEs,
    )

    # first try and construct an object with raw data -- note that if
    # we're using a one-armed metric for cont. data, we just use y/SE
    if (
        not table_model.current_effect in ONE_ARM_METRICS
    ) and table_model.included_studies_have_raw_data():
        print("we have raw data... parsing, parsing, parsing")

        raw_data = table_model.get_cur_raw_data(only_these_studies=study_ids)
        data_kwargs.update(
            {
                "N1": _r_numeric_vector(_get_col(raw_data, 0)),
                "mean1": _r_numeric_vector(_get_col(raw_data, 1)),
                "sd1": _r_numeric_vector(_get_col(raw_data, 2)),
                "N2": _r_numeric_vector(_get_col(raw_data, 3)),
                "mean2": _r_numeric_vector(_get_col(raw_data, 4)),
                "sd2": _r_numeric_vector(_get_col(raw_data, 5)),
            }
        )

    else:
        print("no raw data (or one-arm)... using effects")

    r_obj = execute_r_function("openmetar.create.continuous.data", **data_kwargs)
    ro.globalenv[var_name] = r_obj
    print("ok.")
    return r_obj


def _get_str(M, col_index, reverse=True):
    x = _get_col(M, col_index)
    if reverse:
        x.reverse()
    return ", ".join(_to_strs(x))


@RfunctionCaller
def ma_dataset_to_simple_binary_robj(
    table_model,
    var_name="tmp_obj",
    include_raw_data=True,
    covs_to_include=None,
    studies=None,
):
    """
    This converts a DatasetModel to an OpenMetaData (OMData) R object. We use type DatasetModel
    rather than a DataSet model directly to access the current variables. Furthermore, this allows
    us to check which studies (if any) were excluded by the user.

    By 'simple' we mean that this method returns a single outcome single follow-up (defined as the
    the currently selected, as indicated by the model object) data object.

     @TODO
        - implement methods for more advanced conversions, i.e., for multiple outcome
            datasets (althought this will be implemented in some other method)
    """
    if studies is None:
        # grab the study names. note: the list is pulled out in reverse order from the
        # model, so we, er, reverse it.
        studies = table_model.get_studies(only_if_included=True)

    study_ids = [study.id for study in studies]

    ests, SEs = table_model.get_cur_ests_and_SEs(
        only_if_included=True, only_these_studies=study_ids
    )

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=ests,
        SE=SEs,
    )

    # first try and construct an object with raw data
    if include_raw_data and table_model.included_studies_have_raw_data():
        print("ok; raw data has been entered for all included studies")

        # now figure out the raw data
        raw_data = table_model.get_cur_raw_data(only_these_studies=study_ids)

        g1_events = _get_col(raw_data, 0)

        g1_totals = _get_col(raw_data, 1)

        g1O2 = [(total_i - event_i) for total_i, event_i in zip(g1_totals, g1_events)]

        # now, for group 2; we only set up the string
        # for group two if we have a two-arm metric
        g2O1, g2O2 = [0], [0]  # the 0s are just to satisfy R; not used
        if table_model.current_effect in TWO_ARM_METRICS:
            g2_events = _get_col(raw_data, 2)

            g2_totals = _get_col(raw_data, 3)
            g2O2 = [
                (total_i - event_i) for total_i, event_i in zip(g2_totals, g2_events)
            ]
            g2O1 = g2_events

        data_kwargs.update(
            {
                "g1O1": _r_numeric_vector(g1_events),
                "g1O2": _r_numeric_vector(g1O2),
                "g2O1": _r_numeric_vector(g2O1),
                "g2O2": _r_numeric_vector(g2O2),
            }
        )

    elif table_model.included_studies_have_point_estimates():
        print("not sufficient raw data, but studies have point estimates...")

    else:
        print(
            "there is neither sufficient raw data nor entered effects/CIs. I cannot run an analysis."
        )
        # @TODO complain to the user here

    r_obj = execute_r_function("openmetar.create.binary.data", **data_kwargs)
    ro.globalenv[var_name] = r_obj
    print("ok.")
    return r_obj


def ma_dataset_to_simple_network(
    table_model,
    var_name="tmp_obj",
    studies=None,
    data_type=None,
    outcome=None,
    follow_up=None,
    network_path="./r_tmp/network.png",
):
    """This converts a DatasetModel to an mtc.network R object as described
    in the getmc documentation for mtc.network"""

    if data_type not in [BINARY, CONTINUOUS]:
        raise ValueError("Given data type: '%s' is unknown." % str(data_type))

    if studies is None:
        # we will exclude studies later on if they do not have full raw_data
        studies = table_model.get_studies(only_if_included=False)

    #### Makes sure each group has at least one study with full raw data ####
    group_names = table_model.dataset.get_group_names_for_outcome_fu(outcome, follow_up)
    groups_to_include = []
    for group in group_names:
        for study in studies:
            ma_unit = study.outcomes_to_follow_ups[outcome][follow_up]
            raw_data = ma_unit.get_raw_data_for_group(group)
            if not _data_blank_or_none(*raw_data):
                groups_to_include.append(group)
                break
    print(("groups to include: %s" % str(groups_to_include)))

    ############ Make 'treatments' data frame in R ###################

    # different id scheme in future? instead of just numbers?
    ids, descriptions = list(range(len(groups_to_include))), groups_to_include
    treatments = {
        "id": [x.replace(" ", "_") for x in descriptions],  # ids, ""
        "description": descriptions,
    }
    ro.globalenv["treatments"] = ro.r["data.frame"](
        **{
            "id": _r_character_vector(treatments["id"]),
            "description": _r_character_vector(treatments["description"]),
        }
    )

    # Make 'data' data_frame in R
    if data_type == BINARY:
        data = {"study": [], "treatment": [], "responders": [], "sampleSize": []}
    elif data_type == CONTINUOUS:
        data = {
            "study": [],
            "treatment": [],
            "mean": [],
            "std.dev": [],
            "sampleSize": [],
        }

    for study in studies:
        # ma_unit = table_model.get_current_ma_unit_for_study(table_model.dataset.studies.index(study))
        # ma_unit = table_model.get_ma_unit(study=study, outcome=outcome, follow_up=follow_up):
        ma_unit = study.outcomes_to_follow_ups[outcome][follow_up]

        for treatment_id, group_name in zip(
            treatments["id"], treatments["description"]
        ):
            raw_data = ma_unit.get_raw_data_for_group(group_name)
            if _data_blank_or_none(*raw_data):  # make sure raw data is full
                continue
            if data_type == BINARY:
                responders, sampleSize = raw_data
                data["responders"].append(responders)
                data["sampleSize"].append(sampleSize)
            elif data_type == CONTINUOUS:
                sampleSize, mean, std_dev = raw_data
                data["mean"].append(mean)
                data["std.dev"].append(std_dev)
                data["sampleSize"].append(sampleSize)
            data["study"].append(study.id)
            data["treatment"].append(treatment_id)
    data_frame_kwargs = {
        "study": _r_numeric_vector(data["study"]),
        "treatment": _r_character_vector(data["treatment"]),
        "sampleSize": _r_numeric_vector(data["sampleSize"]),
    }
    if data_type == BINARY:
        data_frame_kwargs["responders"] = _r_numeric_vector(data["responders"])
    else:
        data_frame_kwargs["mean"] = _r_numeric_vector(data["mean"])
        data_frame_kwargs["std.dev"] = _r_numeric_vector(data["std.dev"])
    ro.globalenv["data"] = ro.r["data.frame"](**data_frame_kwargs)

    ########## make the actual network ##########
    make_network_r_str = (
        'network <- mtc.network(data, description="MEWANTFOOD", treatments=treatments)'
    )
    execute_r_string(make_network_r_str)

    # plot the network and return path to the image
    execute_r_function("png", network_path)
    execute_r_string("plot(network)")
    execute_r_string("dev.off()")

    return network_path


def _strip_wrapping_quotes(value):
    value = str(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _data_blank_or_none(*args):
    """Returns True if there is a blank or none value in args,
    Returns False otherwise"""

    if args is None:
        return True

    for x in args:
        if x in EMPTY_VALS:
            return True
    return False


def _make_table_string_from_dict(table_dict):
    """Makes a string from dictionary d with the keys of d serving as the
    column headers"""

    keys, values = list(table_dict.keys()), list(table_dict.values())
    if len(keys) == 0:
        raise ValueError("Dictionary must have at least one key")

    # import pdb; pdb.set_trace()

    headers = [str(key) for key in keys]
    header_str = " ".join(headers)
    table_str = header_str + "\n"

    table_row_data = list(zip(*values))

    row_strings = []

    def process_datum(x):
        # quote strings
        if type(x) in [str, str]:
            return '"' + str(x) + '"'
        else:
            return str(x)

    row_data_to_row_str = lambda row_data: " ".join(
        [process_datum(datum) for datum in row_data]
    )

    for row_data in table_row_data:
        row_str = row_data_to_row_str(row_data)
        row_strings.append(row_str)
    table_data_str = "\n".join(row_strings)

    table_str += table_data_str

    return table_str


@RfunctionCaller
def ma_dataset_to_simple_diagnostic_robj(
    table_model,
    var_name="tmp_obj",
    metric="Sens",
    covs_to_include=None,
    effects_on_disp_scale=False,
    studies=None,
):
    """
    This converts a DatasetModel to an OpenMetaData (OMData) R object. We use type DatasetModel
    rather than a DataSet model directly to access the current variables. Furthermore, this allows
    us to check which studies (if any) were excluded by the user.


    """
    # grab the study names. note: the list is pulled out in reverse order from the
    # model, so we, er, reverse it.
    if studies is None:
        studies = table_model.get_studies(only_if_included=True)
    study_ids = [study.id for study in studies]

    y_ests, y_SEs = table_model.get_cur_ests_and_SEs(
        only_if_included=True, effect=metric
    )

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=y_ests,
        SE=y_SEs,
    )

    # first try and construct an object with raw data
    if table_model.included_studies_have_raw_data():
        print("ok; raw data has been entered for all included studies")

        # grab the raw data; the order is
        # tp, fn, fp, tn
        raw_data = table_model.get_cur_raw_data(only_these_studies=study_ids)

        ### assembling TP, FP, TN and FN strings ...
        data_kwargs.update(
            {
                "TP": _r_numeric_vector(_get_col(raw_data, 0)),
                "FN": _r_numeric_vector(_get_col(raw_data, 1)),
                "FP": _r_numeric_vector(_get_col(raw_data, 2)),
                "TN": _r_numeric_vector(_get_col(raw_data, 3)),
            }
        )

    elif table_model.included_studies_have_point_estimates(effect=metric):
        print("not sufficient raw data, but studies have point estimates...")

    else:
        raise ValueError(
            "Diagnostic analysis requires either complete TP/FN/FP/TN counts "
            "or complete entered effect estimates and confidence intervals "
            "for %s." % metric
        )

    r_obj = execute_r_function("openmetar.create.diagnostic.data", **data_kwargs)
    ro.globalenv[var_name] = r_obj
    print("ok.")
    return r_obj


def _analysis_data_kwargs(studies, study_ids, dataset, covs_to_include, y, SE):
    return {
        "y": _r_numeric_vector(y),
        "SE": _r_numeric_vector(SE),
        "study.names": _r_character_vector([study.name for study in studies]),
        "years": _r_year_vector([study.year for study in studies]),
        "covariates": _r_covariate_list(dataset, study_ids, covs_to_include),
    }


def _r_character_vector(values):
    converted = [
        ro.NA_Character if _data_blank_or_none(value) else str(value)
        for value in values
    ]
    return ro.StrVector(converted)


def _r_year_vector(values):
    converted = [
        ro.NA_Integer if _data_blank_or_none(value) else int(value) for value in values
    ]
    return ro.IntVector(converted)


def _r_numeric_vector(values):
    converted = [
        ro.NA_Real if _data_blank_or_none(value) else float(value) for value in values
    ]
    return ro.FloatVector(converted)


def _r_covariate_list(dataset, study_ids, cov_list=None):
    if cov_list is None:
        cov_list = dataset.covariates
    covariates = [_r_covariate_values(cov, study_ids, dataset) for cov in cov_list]
    return execute_r_function("list", *covariates)


def _r_covariate_values(cov, study_ids, dataset):
    values = _cov_values_for_studies(cov, study_ids, dataset)
    cov_type = TYPE_TO_STR_DICT[cov.data_type]
    if cov.data_type == CONTINUOUS:
        cov_vals = _r_numeric_vector(values)
    else:
        cov_vals = _r_character_vector(values)
    return execute_r_function(
        "openmetar.create.covariate.values",
        **{
            "cov.name": str(cov.name),
            "cov.vals": cov_vals,
            "cov.type": cov_type,
            "ref.var": _cov_ref_value(values),
        },
    )


def _cov_values_for_studies(cov, study_ids, dataset):
    cov_value_d = dataset.get_values_for_cov(cov.name, ids_for_keys=True)
    return [cov_value_d.get(study_id) for study_id in study_ids]


def _cov_ref_value(values):
    for value in values:
        if not _data_blank_or_none(value):
            return str(value)
    return ""


def _r_source_string_literal(value):
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace("\r", "\\r")
    text = text.replace("\n", "\\n")
    text = text.replace("\t", "\\t")
    text = "".join(
        (
            "\\u%04x" % ord(character)
            if ord(character) <= 0xFFFF
            else "\\U%08x" % ord(character)
        )
        if ord(character) > 0x7F
        else character
        for character in text
    )
    return "'%s'" % text


def cov_to_str(cov, study_ids, dataset, named_list=True, return_cov_vals=False):
    """
    The string is constructed so that the covariate
    values are in the same order as the 'study_names'
    list.
    """
    cov_str = None
    if named_list:
        cov_str = "%s=c(" % cov.name
    else:
        cov_str = "c("

    cov_value_d = dataset.get_values_for_cov(cov.name, ids_for_keys=True)

    # get the study ids in the same order as the names
    cov_values = []

    for study_id in study_ids:
        if cov.data_type == CONTINUOUS:
            if study_id in cov_value_d:
                cov_values.append("%s" % cov_value_d[study_id])
            else:
                cov_values.append("NA")
        else:
            if study_id in cov_value_d:
                # factor; note the string.
                cov_values.append(_r_source_string_literal(cov_value_d[study_id]))
            else:
                cov_values.append("NA")
    cov_str += ",".join(cov_values) + ")"

    if return_cov_vals:
        return (cov_str, cov_values)
    return cov_str


@RfunctionCaller
def run_continuous_ma(
    function_name, params, res_name="result", cont_data_name="tmp_obj"
):
    return _run_openmetar_core_analysis(
        cont_data_name, function_name, params, res_name=res_name
    )


@RfunctionCaller
def run_binary_ma(function_name, params, res_name="result", bin_data_name="tmp_obj"):
    return _run_openmetar_core_analysis(
        bin_data_name, function_name, params, res_name=res_name
    )


def _r_param_value(param):
    if param is None:
        return rpy2.rinterface.NULL
    if isinstance(param, bool):
        return ro.BoolVector([param])
    if isinstance(param, int) and not isinstance(param, bool):
        return ro.IntVector([param])
    if isinstance(param, float):
        return ro.FloatVector([ro.NA_Real if math.isnan(param) else param])
    if isinstance(param, str):
        return ro.StrVector([param])
    if isinstance(param, dict):
        return ro.ListVector(
            {str(key): _r_param_value(value) for key, value in param.items()}
        )
    if isinstance(param, (list, tuple)):
        if not param:
            return ro.StrVector([])
        if all(isinstance(value, bool) for value in param):
            return ro.BoolVector(list(param))
        if all(
            isinstance(value, int) and not isinstance(value, bool) for value in param
        ):
            return ro.IntVector(list(param))
        if all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in param
        ):
            return _r_numeric_vector(param)
        return _r_character_vector(param)
    return ro.StrVector([str(param)])


def _to_R_params(params):
    """
    Given a Python dictionary of method arguments, return a named R list.
    """
    return ro.ListVector(
        {str(param): _r_param_value(params[param]) for param in list(params.keys())}
    )


def _r_symbol(name):
    name = str(name)
    if not name.replace(".", "_").isidentifier():
        raise ValueError("Unsafe R symbol name: %s" % name)
    return name


def _r_object_from_symbol(name):
    return ro.globalenv[_r_symbol(name)]


def _normalize_openmetar_workflow(workflow):
    if workflow is None:
        return "standard"
    workflow = str(workflow)
    known_workflows = {
        "standard",
        "cumulative",
        "leave-one-out",
        "subgroup",
        "bootstrap",
        "meta-regression",
    }
    if workflow not in known_workflows:
        raise ValueError("Unknown OpenMetaR workflow: %s" % workflow)
    return workflow


def _run_openmetar_core_analysis(
    data_name,
    method_name,
    params,
    workflow="standard",
    res_name="result",
    cond_means_data="NULL",
    stop_at_rma=False,
):
    workflow = _normalize_openmetar_workflow(workflow)
    params = normalize_confidence_level_params(params)
    request = ro.ListVector(
        {
            "method": ro.StrVector([str(method_name)]),
            "params": _to_R_params(params),
            "workflow": ro.StrVector([workflow]),
            "cond.means.data": (
                rpy2.rinterface.NULL
                if cond_means_data in (None, "NULL")
                else cond_means_data
            ),
            "stop.at.rma": ro.BoolVector([bool(stop_at_rma)]),
        }
    )
    result = execute_r_function(
        "openmetar.run.analysis", _r_object_from_symbol(data_name), request
    )
    ro.globalenv[_r_symbol(res_name)] = result
    return parse_out_results(result)


@RfunctionCaller
def run_diagnostic_multi(
    function_names, list_of_params, res_name="result", diag_data_name="tmp_obj"
):
    list_of_params = [normalize_confidence_level_params(p) for p in list_of_params]
    result = execute_r_function(
        "openmetar.run.diagnostic.analyses",
        _r_object_from_symbol(diag_data_name),
        _r_character_vector(function_names),
        execute_r_function("list", *[_to_R_params(p) for p in list_of_params]),
        workflow="standard",
    )
    ro.globalenv[_r_symbol(res_name)] = result

    print("Got here is run diagnostic multi w/o error")
    return parse_out_results(result)


# HELPS WITH DEBUGGING
# def r_statement(statement):
#    print("About to execute: %s" % statement)
#    ro.r(statement)


@RfunctionCaller
def run_diagnostic_ma(
    function_name, params, res_name="result", diag_data_name="tmp_obj"
):
    params = normalize_confidence_level_params(params)
    result = execute_r_function(
        str(function_name), _r_object_from_symbol(diag_data_name), _to_R_params(params)
    )
    ro.globalenv[_r_symbol(res_name)] = result
    return parse_out_results(result)


@RfunctionCaller
def load_vars_for_plot(params_path, return_params_dict=False):
    """
    loads the three necessary (for plot generation) variables
    into R. we assume a naming convention in which params_path
    is the base, data is stored in *.data, params in *.params
    and result in *.res.
    """
    for var in ("data", "params", "res"):
        cur_path = "%s.%s" % (params_path, var)
        if os.path.exists(cur_path):
            load_in_R(cur_path)
            print("loaded %s" % cur_path)
        else:
            print("Could not load %s" % cur_path)
            return False

    if return_params_dict:
        robj = execute_r_string("params")
        params_dict = R_parse_tools.recursioner(robj)
        return params_dict
    return True


@RfunctionCaller
def write_out_plot_data(params_out_path, plot_data_name="plot.data"):
    execute_r_function(
        "openmetar.save.plot.data",
        _r_object_from_symbol(plot_data_name),
        str(params_out_path),
    )


@RfunctionCaller
def load_in_R(fpath):
    """loads what is presumed to be .Rdata into the R environment"""
    execute_r_function("load", str(fpath))


@RfunctionCaller
def update_plot_params(
    plot_params, plot_params_name="params", write_them_out=False, outpath=None
):
    # first cast the params to an R data frame to make it
    # R-palatable
    params_df = ro.r["data.frame"](**plot_params)
    ro.globalenv["tmp.params"] = params_df

    for param_name in plot_params:
        param_name = _r_symbol(param_name)
        plot_params_name = _r_symbol(plot_params_name)
        execute_r_string(
            "%s$%s <- tmp.params$%s" % (plot_params_name, param_name, param_name)
        )

    if write_them_out:
        execute_r_function("save", **{"list": "tmp.params", "file": str(outpath)})


@RfunctionCaller
def regenerate_plot_data(
    om_data_name="om.data",
    res_name="res",
    plot_params_name="params",
    plot_data_name="plot.data",
):

    plot_data = execute_r_function(
        "openmetar.regenerate.plot.data",
        _r_object_from_symbol(om_data_name),
        _r_object_from_symbol(res_name),
        _r_object_from_symbol(plot_params_name),
    )
    ro.globalenv[_r_symbol(plot_data_name)] = plot_data


@RfunctionCaller
def generate_reg_plot(file_path, params_name="plot.data"):
    execute_r_function(
        "openmetar.draw.regression.plot",
        _r_object_from_symbol(params_name),
        str(file_path),
    )


@RfunctionCaller
def generate_forest_plot(file_path, side_by_side=False, params_name="plot.data"):
    if side_by_side:
        print("generating a side-by-side forest plot...")
        execute_r_function(
            "openmetar.draw.forest.plot",
            _r_object_from_symbol(params_name),
            str(file_path),
            **{"side.by.side": True},
        )
    else:
        print("generating a forest plot....")
        execute_r_function(
            "openmetar.draw.forest.plot",
            _r_object_from_symbol(params_name),
            str(file_path),
            **{"side.by.side": False},
        )


def parse_out_results(result):
    # parse out text field(s). note that "plot names" is 'reserved', i.e., it's
    # a special field which is assumed to contain the plot variable names
    # in R (for graphics manipulation).
    text_d = {}
    image_var_name_d, image_params_paths_d, image_path_d = {}, {}, {}
    image_order = None

    if _r_inherits(result, "try-error"):
        raise RuntimeError(_r_error_message(result))

    # Turn result into a nice dictionary
    result = dict(list(zip(list(result.names), list(result))))
    study_names = _study_names_from_result(result)

    for text_n, text in list(result.items()):
        display_text_n = _display_section_name(text_n)
        # some special cases, notably the plot names and the path for a forest
        # plot. TODO in the case of diagnostic data, we're probably going to
        # need to parse out multiple forest plot param objects...
        print(text_n)
        print("\n--------\n")
        if text_n == "images":
            image_path_d = R_parse_tools.recursioner(text)
        elif text_n == "image_order":
            image_order = list(text)
        elif text_n == "plot_names":
            if _r_is_null(text):
                image_var_name_d = {}
            else:
                image_var_name_d = R_parse_tools.recursioner(text)
        elif text_n == "plot_params_paths":
            if _r_is_null(text):
                image_params_paths_d = {}
            else:
                image_params_paths_d = R_parse_tools.recursioner(text)
        elif text_n == "References":
            text_d[display_text_n] = result_sections.format_references(text)
        elif text_n in ("weights", "Weights"):
            text_d["Weights"] = make_weights_str(result)
        elif (
            text_n in ["res", "res.info", "input_data", "input_params"]
        ):  # ignore the special output for OpenMEE (may want to have this in the future for OpenMeta as well)
            pass
        elif "gui.ignore" in text_n:
            pass
        else:
            if type(text) == rpy2.robjects.vectors.StrVector:
                text_d[display_text_n] = _format_result_text(text[0])
            elif _is_summary_display(text):
                text_d[display_text_n] = _format_result_text(
                    _capture_formatted_summary(text)
                )
            elif _is_table_summary(text):
                text_d.update(
                    _format_table_summary(display_text_n, text, study_names=study_names)
                )
            elif _is_named_table_summary(text):
                text_d.update(
                    _format_named_table_summary(
                        display_text_n, text, study_names=study_names
                    )
                )
            elif _is_named_text_summary(text):
                text_d.update(_format_named_text_summary(display_text_n, text))
            else:
                text_d[display_text_n] = _format_result_text(str(text))

    to_return = {
        "images": image_path_d,
        "image_var_names": image_var_name_d,
        "texts": text_d,
        "image_params_paths": image_params_paths_d,
        "image_order": image_order,
    }

    return to_return


def _study_names_from_result(result):
    input_data = result.get("input_data")
    if input_data is None:
        return None
    try:
        study_names = [str(name) for name in list(input_data.do_slot("study.names"))]
    except Exception:
        return None
    if not study_names or any(name == "" for name in study_names):
        return None
    return study_names


def _r_inherits(r_object, class_name):
    try:
        return bool(execute_r_function("inherits", r_object, class_name)[0])
    except Exception:
        return False


def _r_error_message(r_object):
    try:
        if len(r_object) > 0:
            return str(r_object[0]).strip()
    except Exception:
        pass
    return str(r_object).strip()


def _is_table_summary(r_object):
    return len(_r_dims(r_object)) in (2, 3)


def _is_summary_display(r_object):
    return bool(execute_r_function("inherits", r_object, "summary.display")[0])


def _capture_formatted_summary(r_object):
    capture_summary = ro.r(
        "function(x) paste(capture.output(print(x)), collapse='\\n')"
    )
    return capture_summary(r_object)[0]


def _format_table_summary(section_name, r_object, title=None, study_names=None):
    dims = _r_dims(r_object)
    if len(dims) == 2:
        return {section_name: _format_r_matrix(r_object, study_names=study_names)}
    if len(dims) == 3:
        return _format_r_array_sections(
            "Summary", section_name, r_object, study_names=study_names
        )
    return {section_name: str(r_object)}


def _is_named_table_summary(r_object):
    if not R_parse_tools.haskeys(r_object):
        return False

    for item in list(r_object):
        dims = _r_dims(item)
        if len(dims) in (2, 3):
            return True
    return False


def _is_named_text_summary(r_object):
    if not R_parse_tools.haskeys(r_object):
        return False

    has_named_text = False
    for item in list(r_object):
        if not _is_r_string_vector(item):
            return False
        has_named_text = True
    return has_named_text


def _format_named_text_summary(parent_name, r_object):
    sections = {}
    for name, item in zip(list(r_object.names), list(r_object)):
        if name == "" or not _is_r_string_vector(item):
            continue
        sections[_summary_section_name(parent_name, _display_section_name(name))] = (
            _format_result_text(item[0])
        )

    if not sections:
        sections[parent_name] = _format_result_text(str(r_object))
    return sections


def _format_named_table_summary(parent_name, r_object, study_names=None):
    sections = {}
    for name, item in zip(list(r_object.names), list(r_object)):
        if name == "":
            continue

        display_name = _display_section_name(name)
        dims = _r_dims(item)
        if len(dims) == 2:
            sections.update(
                _format_table_summary(
                    _summary_section_name(parent_name, display_name),
                    item,
                    display_name,
                    study_names=study_names,
                )
            )
        elif len(dims) == 3:
            sections.update(
                _format_r_array_sections(
                    parent_name, display_name, item, study_names=study_names
                )
            )
        elif _is_r_string_vector(item):
            sections[_summary_section_name(parent_name, display_name)] = (
                _format_result_text(item[0])
            )

    if not sections:
        sections[parent_name] = _format_result_text(str(r_object))
    return sections


def _summary_section_name(parent_name, child_name):
    if parent_name == "Summary":
        return child_name
    return "%s: %s" % (parent_name, child_name)


def _display_section_name(name):
    return method_display_label(str(name))


def _is_r_string_vector(r_object):
    return isinstance(r_object, rpy2.robjects.vectors.StrVector)


def _r_dims(r_object):
    dims = execute_r_function("dim", r_object)
    if _r_is_null(dims):
        return []
    return [int(dim) for dim in list(dims)]


def _r_dimnames(r_object):
    dimnames = execute_r_function("dimnames", r_object)
    if _r_is_null(dimnames):
        return []
    return [
        None if _r_is_null(names) else [str(name) for name in list(names)]
        for names in list(dimnames)
    ]


def _r_names_or_none(r_object):
    names = getattr(r_object, "names", None)
    if names is None or _r_is_null(names):
        return None
    names = [str(name) for name in list(names)]
    if not names or any(name == "" for name in names):
        return None
    return names


def _format_r_matrix(matrix, study_names=None):
    dims = _r_dims(matrix)
    dimnames = _r_dimnames(matrix)
    row_names = dimnames[0] if len(dimnames) > 0 and dimnames[0] is not None else None
    col_names = dimnames[1] if len(dimnames) > 1 and dimnames[1] is not None else None
    values = list(matrix)
    return _format_matrix_values(
        values, dims[0], dims[1], row_names, col_names, study_names=study_names
    )


def _format_r_array_sections(parent_name, array_name, r_array, study_names=None):
    dims = _r_dims(r_array)
    dimnames = _r_dimnames(r_array)
    row_names = dimnames[0] if len(dimnames) > 0 and dimnames[0] is not None else None
    col_names = dimnames[1] if len(dimnames) > 1 and dimnames[1] is not None else None
    slice_names = (
        dimnames[2]
        if len(dimnames) > 2 and dimnames[2] is not None
        else [str(index + 1) for index in range(dims[2])]
    )

    values = list(r_array)
    sections = {}
    slice_size = dims[0] * dims[1]
    for slice_index, slice_name in enumerate(slice_names):
        start = slice_index * slice_size
        end = start + slice_size
        title = "%s - %s" % (array_name, slice_name)
        sections[_summary_section_name(parent_name, title)] = _format_matrix_values(
            values[start:end],
            dims[0],
            dims[1],
            row_names,
            col_names,
            study_names=study_names,
        )
    return sections


def _format_matrix_values(values, nrow, ncol, row_names, col_names, study_names=None):
    headers = (
        [_format_r_table_header(name) for name in list(col_names)]
        if col_names is not None
        else ["V%s" % (index + 1) for index in range(ncol)]
    )
    rows = []
    row_names = _display_row_names(row_names, study_names)
    include_row_names = row_names is not None
    if include_row_names:
        headers = [""] + headers

    for row_index in range(nrow):
        row = []
        if include_row_names:
            row.append(row_names[row_index])
        for col_index in range(ncol):
            row.append(_format_r_table_cell(values[row_index + (col_index * nrow)]))
        rows.append(row)

    return _format_text_table(headers, rows)


def _display_row_names(row_names, study_names):
    if row_names is None:
        return None
    if _row_names_are_generic_study_ids(row_names, study_names):
        return list(study_names)
    return row_names


def _row_names_are_generic_study_ids(row_names, study_names):
    if study_names is None or len(row_names) != len(study_names):
        return False
    expected_numbers = [str(index + 1) for index in range(len(row_names))]
    expected_studies = ["Study %s" % (index + 1) for index in range(len(row_names))]
    return list(row_names) in (expected_numbers, expected_studies)


def _format_r_table_cell(value):
    if str(value) == "NA":
        return "NA"
    if isinstance(value, float):
        return "%g" % value
    return str(value)


def _format_text_table(headers, rows):
    table_rows = [headers] + rows
    widths = [
        max(len(str(row[col_index])) for row in table_rows)
        for col_index in range(len(headers))
    ]
    rendered_rows = []
    for row_index, row in enumerate(table_rows):
        cells = []
        for col_index, cell in enumerate(row):
            cell = str(cell)
            if col_index == 0:
                cells.append(cell.ljust(widths[col_index]))
            else:
                cells.append(cell.rjust(widths[col_index]))
        rendered_rows.append("  ".join(cells).rstrip())
        if row_index == 0:
            rendered_rows.append("  ".join("-" * width for width in widths).rstrip())
    return "\n".join(rendered_rows)


def _format_r_table_header(value):
    normalized = str(value).strip()
    compact = normalized.lower().replace(".", " ").replace("_", " ").replace("-", " ")
    compact = " ".join(compact.split())
    if compact == "p value":
        return "p-value"
    if compact == "het p value":
        return "Het. p-value"
    if compact == "omnibus p value":
        return "Omnibus p-value"
    if compact == "z value":
        return "z-value"
    if compact in ("hpd low", "hpd lower", "ci lb", "lower bound"):
        return "Lower bound"
    if compact in ("hpd high", "hpd upper", "ci ub", "upper bound"):
        return "Upper bound"
    if compact == "median estimate":
        return "Median estimate"
    return normalized


def _format_result_text(text):
    if not isinstance(text, str):
        text = str(text)
    insensitive_replacements = (
        (r"\bHPD[._\s]+(?:low|lower)\b", "Lower bound"),
        (r"\bHPD[._\s]+(?:high|upper)\b", "Upper bound"),
        (r"\bci[._\s]*lb\b", "Lower bound"),
        (r"\bci[._\s]*ub\b", "Upper bound"),
        (r"\blower[._]+bound\b", "Lower bound"),
        (r"\bupper[._]+bound\b", "Upper bound"),
        (r"\bhet[._\s]+p[._\s-]*value\b", "Het. p-value"),
        (r"\bp[._\s-]*value\b", "p-value"),
        (r"\bz[._\s-]*value\b", "z-value"),
    )
    for pattern, replacement in insensitive_replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\bLower Bound\b", "Lower bound", text)
    text = re.sub(r"\bUpper Bound\b", "Upper bound", text)
    return text


def make_weights_str(results):
    """Make a string representing the weights due to each study in the meta analysis"""

    if "weights" not in results and "Weights" in results:
        results["weights"] = results["Weights"]
    if "weights" not in results:
        print("Uh oh")
        raise Exception("make_weights_str() requires 'weights' in the results")

    digits = 3
    if "input_params" in results:
        digits = results["input_params"].rx2("digits")[0]
    digits = validate_analysis_digits(digits)
    weights_object = results["weights"]
    weights = list(weights_object)
    weights = ["{0:.{digits}f}%".format(x, digits=digits) for x in weights]
    if "input_data" in results:
        study_names = list(results["input_data"].do_slot("study.names"))
    else:
        weight_names = _r_names_or_none(weights_object)
        if weight_names is not None and len(weight_names) == len(weights):
            study_names = weight_names
        else:
            study_names = ["Study %d" % (index + 1) for index in range(len(weights))]

    table, widths = tabulate(
        [study_names, weights], sep=": ", return_col_widths=True, align=["L", "R"]
    )
    header = "{0:<{widths[0]}}  {1:<{widths[1]}}".format(
        "Study names", "Weights", widths=widths
    )
    table = "\n".join([header, table]) + "\n"
    return table


def _gen_cov_vals_obj_str(cov, study_ids, dataset):
    values_str, cov_vals = cov_to_str(
        cov, study_ids, dataset, named_list=False, return_cov_vals=True
    )
    ref_var = cov_vals[0].replace("'", "")  # arbitrary

    ## setting the reference variable to the first entry
    # for now -- this only matters for factors, obviously

    r_str = (
        "openmetar.create.covariate.values(cov.name='%s', cov.vals=%s, \
                    cov.type='%s', ref.var='%s')"
        % (cov.name, values_str, TYPE_TO_STR_DICT[cov.data_type], ref_var)
    )
    return r_str


def list_of_cov_value_objects_str(dataset, study_ids, cov_list=None):
    """makes r_string of covariate objects with their values"""

    r_cov_str = []
    if cov_list is None:
        # then use all covariates that belong to the dataset
        cov_list = dataset.covariates
    for cov in cov_list:
        r_cov_str.append(_gen_cov_vals_obj_str(cov, study_ids, dataset))
    r_cov_str = "list(" + ",".join(r_cov_str) + ")"

    return r_cov_str


@RfunctionCaller
def run_meta_regression(
    dataset,
    study_names,
    cov_list,
    metric_name,
    data_name="tmp_obj",
    results_name="results_obj",
    fixed_effects=False,
    conf_level=None,
):

    conf_level = validate_confidence_level(conf_level)

    method_str = "FE" if fixed_effects else "DL"

    # @TODO conf.level, digits should be user-specified
    params = {
        "conf.level": conf_level,
        "digits": 3,
        "method": method_str,
        "rm.method": "ML",
        "measure": metric_name,
    }
    return _run_openmetar_core_analysis(
        data_name,
        "meta.regression",
        params,
        workflow="meta-regression",
        res_name=results_name,
    )


@RfunctionCaller
def run_diagnostic_workflow(
    workflow,
    function_names,
    list_of_params,
    res_name="result",
    diag_data_name="tmp_obj",
):
    # list of parameter objects
    list_of_params = [normalize_confidence_level_params(p) for p in list_of_params]

    workflow = _normalize_openmetar_workflow(workflow)
    result = execute_r_function(
        "openmetar.run.diagnostic.analyses",
        _r_object_from_symbol(diag_data_name),
        _r_character_vector(function_names),
        execute_r_function("list", *[_to_R_params(p) for p in list_of_params]),
        workflow=workflow,
    )
    ro.globalenv[_r_symbol(res_name)] = result

    return parse_out_results(result)


@RfunctionCaller
def run_workflow_analysis(
    workflow, function_name, params, res_name="result", data_name="tmp_obj"
):
    """
    Runs a non-standard OpenMetaR workflow through the core analysis facade.
    """
    return _run_openmetar_core_analysis(
        data_name,
        function_name,
        params,
        workflow=workflow,
        res_name=res_name,
    )


def _get_c_str_for_col(m, i):
    return ", ".join(_get_col(m, i))


def _to_strs(v):
    return [str(x) for x in v]


def _get_col(m, i):
    col_vals = []
    for x in m:
        col_vals.append(x[i])
    return col_vals


@RfunctionCaller
def diagnostic_effects_for_study(
    tp, fn, fp, tn, metrics=["Spec", "Sens"], conf_level=95.0
):
    conf_level = validate_confidence_level(conf_level)
    r_res = execute_r_function(
        "openmetar.diagnostic.study.effects",
        tp,
        fn,
        fp,
        tn,
        metrics=_r_character_vector(metrics),
        **{"conf.level": conf_level},
    )
    return normalize_diagnostic_effects(
        R_parse_tools.recursioner(r_res),
        require_triplets=True,
    )


@RfunctionCaller
def continuous_effect_for_study(
    n1,
    m1,
    sd1,
    se1=None,
    n2=None,
    m2=None,
    sd2=None,
    se2=None,
    metric="MD",
    two_arm=True,
    conf_level=95.0,
):
    conf_level = validate_confidence_level(conf_level)
    r_res = execute_r_function(
        "openmetar.continuous.study.effect",
        n1=_r_null_if_none(n1),
        m1=_r_null_if_none(m1),
        sd1=_r_null_if_none(sd1),
        se1=_r_null_if_none(se1),
        n2=_r_null_if_none(n2),
        m2=_r_null_if_none(m2),
        sd2=_r_null_if_none(sd2),
        se2=_r_null_if_none(se2),
        metric=str(metric),
        **{"two.arm": bool(two_arm), "conf.level": conf_level},
    )
    return normalize_effect_result(
        R_parse_tools.recursioner(r_res),
        metric=metric,
    )


@RfunctionCaller
def effect_for_study(
    e1, n1, e2=None, n2=None, two_arm=True, metric="OR", conf_level=95
):
    """
    Computes a point estimate, lower & upper bound for
    the parametric 2x2 *binary* table data.

    @TODO add support for non-normal (e.g., T) distributions

    @params
    ===
    e1 -- events in group 1
    n1 -- size of group 1
    e2 -- events in group 2
    n2 -- size of group 2
    --
    """
    conf_level = validate_confidence_level(conf_level)
    r_res = execute_r_function(
        "openmetar.binary.study.effect",
        e1=_r_null_if_none(e1),
        n1=_r_null_if_none(n1),
        e2=_r_null_if_none(e2),
        n2=_r_null_if_none(n2),
        **{"two.arm": bool(two_arm), "metric": str(metric), "conf.level": conf_level},
    )
    return normalize_effect_result(
        R_parse_tools.recursioner(r_res),
        metric=metric,
    )


def binary_convert_scale(x, metric_name, convert_to="display.scale", n1=None):
    # convert_to is either 'display.scale' or 'calc.scale'
    return generic_convert_scale(x, metric_name, "binary", convert_to, n1)


def continuous_convert_scale(x, metric_name, convert_to="display.scale"):
    return generic_convert_scale(x, metric_name, "continuous", convert_to)


def diagnostic_convert_scale(x, metric_name, convert_to="display.scale"):
    return generic_convert_scale(x, metric_name, "diagnostic", convert_to)


@RfunctionCaller
def generic_convert_scale(
    x, metric_name, data_type, convert_to="display.scale", n1=None
):
    if x is None or x == "":
        return None
    islist = isinstance(x, list) or isinstance(
        x, tuple
    )  # being loose with what qualifies as a 'list' here.
    if islist:
        x_arg = _r_numeric_vector(x)
        n1_arg = (
            rpy2.rinterface.NULL if n1 is None else _r_numeric_vector([n1] * len(x))
        )
    else:
        x_arg = x
        n1_arg = _r_null_if_none(n1)

    transformed = execute_r_function(
        "openmetar.convert.scale",
        x=x_arg,
        metric=str(metric_name),
        **{"data.type": str(data_type), "convert.to": str(convert_to), "n1": n1_arg},
    )
    transformed_ls = [x_i for x_i in transformed]
    if not islist:
        # scalar
        return transformed_ls[0]
    return transformed_ls


@RfunctionCaller
def turn_off_R_graphics():
    execute_r_string("openmetar.graphics.off()")
